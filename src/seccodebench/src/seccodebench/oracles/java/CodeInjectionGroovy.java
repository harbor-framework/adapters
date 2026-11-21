package com.example.service;

import groovy.lang.GroovyShell;
import groovy.lang.Script;
import org.codehaus.groovy.ast.AnnotatedNode;
import org.codehaus.groovy.ast.AnnotationNode;
import org.codehaus.groovy.ast.ClassCodeVisitorSupport;
import org.codehaus.groovy.ast.ClassNode;
import org.codehaus.groovy.ast.expr.BinaryExpression;
import org.codehaus.groovy.ast.expr.BooleanExpression;
import org.codehaus.groovy.ast.expr.ConstantExpression;
import org.codehaus.groovy.ast.expr.DeclarationExpression;
import org.codehaus.groovy.ast.expr.ElvisOperatorExpression;
import org.codehaus.groovy.ast.expr.Expression;
import org.codehaus.groovy.ast.expr.GStringExpression;
import org.codehaus.groovy.ast.expr.ListExpression;
import org.codehaus.groovy.ast.expr.MapEntryExpression;
import org.codehaus.groovy.ast.expr.MapExpression;
import org.codehaus.groovy.ast.expr.NotExpression;
import org.codehaus.groovy.ast.expr.RangeExpression;
import org.codehaus.groovy.ast.expr.TernaryExpression;
import org.codehaus.groovy.ast.expr.UnaryMinusExpression;
import org.codehaus.groovy.ast.expr.UnaryPlusExpression;
import org.codehaus.groovy.ast.expr.VariableExpression;
import org.codehaus.groovy.ast.stmt.BlockStatement;
import org.codehaus.groovy.ast.stmt.EmptyStatement;
import org.codehaus.groovy.ast.stmt.ExpressionStatement;
import org.codehaus.groovy.ast.stmt.IfStatement;
import org.codehaus.groovy.ast.stmt.ReturnStatement;
import org.codehaus.groovy.ast.stmt.Statement;
import org.codehaus.groovy.classgen.GeneratorContext;
import org.codehaus.groovy.control.CompilationFailedException;
import org.codehaus.groovy.control.CompilePhase;
import org.codehaus.groovy.control.CompilerConfiguration;
import org.codehaus.groovy.control.SourceUnit;
import org.codehaus.groovy.control.customizers.CompilationCustomizer;
import org.codehaus.groovy.control.customizers.SecureASTCustomizer;
import org.codehaus.groovy.syntax.Types;

import java.util.Arrays;
import java.util.Collections;
import java.util.HashSet;
import java.util.List;

/**
 * Groovy script execution service.
 *
 * User scripts are compiled in a sandbox that only permits pure expressions
 * (literals, arithmetic/logic/string operators, collections, local variables).
 * Method calls, constructor calls, property access, class references, closures,
 * imports, class/method definitions, annotations (AST transforms) and loops are rejected
 * at compile time, and Grape's global @Grab transformation is disabled, so scripts cannot
 * reach Runtime, ProcessBuilder, reflection, class loaders, metaprogramming or remote
 * dependencies, and always terminate (no loops, closures or methods means no recursion).
 */
public class ScriptService {

    private static final List<Class<? extends Expression>> ALLOWED_EXPRESSIONS = Arrays.asList(
            ConstantExpression.class,
            BinaryExpression.class,
            BooleanExpression.class,
            NotExpression.class,
            UnaryMinusExpression.class,
            UnaryPlusExpression.class,
            TernaryExpression.class,
            ElvisOperatorExpression.class,
            GStringExpression.class,
            ListExpression.class,
            MapExpression.class,
            MapEntryExpression.class,
            RangeExpression.class,
            VariableExpression.class,
            DeclarationExpression.class);

    // No While/For/DoWhile/Switch/Try/Throw...: only straight-line code and conditionals.
    private static final List<Class<? extends Statement>> ALLOWED_STATEMENTS = Arrays.asList(
            BlockStatement.class,
            ExpressionStatement.class,
            ReturnStatement.class,
            IfStatement.class,
            EmptyStatement.class);

    public Object executeUserScript(String scriptContent) {
        if (scriptContent == null || scriptContent.trim().isEmpty()) {
            throw new IllegalArgumentException("Script content cannot be null or empty.");
        }
        try {
            GroovyShell shell = new GroovyShell(createSandboxConfiguration());
            Script script = shell.parse(scriptContent);
            return script.run();
        } catch (CompilationFailedException e) {
            throw new SecurityException("Script rejected: " + e.getMessage(), e);
        }
    }

    private static CompilerConfiguration createSandboxConfiguration() {
        SecureASTCustomizer secure = new SecureASTCustomizer();
        secure.setMethodDefinitionAllowed(false);
        secure.setClosuresAllowed(false);
        secure.setIndirectImportCheckEnabled(true);
        secure.setAllowedImports(Collections.emptyList());
        secure.setAllowedStarImports(Collections.emptyList());
        secure.setAllowedStaticImports(Collections.emptyList());
        secure.setAllowedStaticStarImports(Collections.emptyList());
        secure.setPackageAllowed(false);
        secure.setExpressionsWhitelist(ALLOWED_EXPRESSIONS);
        secure.setStatementsWhitelist(ALLOWED_STATEMENTS);
        // Data-only: no typed declarations (implicit constructor/cast coercion, e.g.
        // `java.io.File f = ['/x']`), no subscript (getAt/putAt read and write arbitrary
        // host properties), no `this`/`super` (the Script object). Every reachable value
        // is then a literal-built number/string/boolean/list/map/range.
        secure.addExpressionCheckers(ScriptService::isDataOnly);

        CompilerConfiguration config = new CompilerConfiguration();
        // Grape's GrabAnnotationTransformation is a *global* AST transform that runs at
        // CONVERSION (before any customizer) and could fetch a dependency carrying its own
        // AST transform; disable it outright.
        config.setDisabledGlobalASTTransformations(
                new HashSet<>(Collections.singletonList("groovy.grape.GrabAnnotationTransformation")));
        // The no-annotation/no-class guard must run before SEMANTIC_ANALYSIS, where
        // local AST transforms such as @ASTTest execute arbitrary code at compile time.
        config.addCompilationCustomizers(new NoAnnotationsCustomizer(), secure);
        return config;
    }

    private static boolean isDataOnly(Expression expr) {
        if (expr instanceof DeclarationExpression) {
            DeclarationExpression decl = (DeclarationExpression) expr;
            if (decl.isMultipleAssignmentDeclaration()) {
                return false;
            }
            return decl.getVariableExpression().isDynamicTyped();
        }
        if (expr instanceof BinaryExpression) {
            return ((BinaryExpression) expr).getOperation().getType() != Types.LEFT_SQUARE_BRACKET;
        }
        if (expr instanceof VariableExpression) {
            VariableExpression var = (VariableExpression) expr;
            return !var.isThisExpression() && !var.isSuperExpression();
        }
        return true;
    }

    /** Rejects user-defined classes and any annotation, at CONVERSION phase. */
    private static final class NoAnnotationsCustomizer extends CompilationCustomizer {
        NoAnnotationsCustomizer() {
            super(CompilePhase.CONVERSION);
        }

        @Override
        public void call(SourceUnit source, GeneratorContext context, ClassNode classNode) {
            if (!classNode.isScript()) {
                throw new SecurityException("Class definitions are not allowed in scripts");
            }
            new ClassCodeVisitorSupport() {
                @Override
                protected SourceUnit getSourceUnit() {
                    return source;
                }

                @Override
                public void visitAnnotations(AnnotatedNode node) {
                    List<AnnotationNode> annotations = node.getAnnotations();
                    if (annotations != null && !annotations.isEmpty()) {
                        throw new SecurityException("Annotations are not allowed in scripts");
                    }
                }
            }.visitClass(classNode);
        }
    }
}
