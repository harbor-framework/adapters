package com.example.service;

import org.w3c.dom.Document;
import org.xml.sax.SAXException;

import javax.xml.XMLConstants;
import javax.xml.parsers.DocumentBuilder;
import javax.xml.parsers.DocumentBuilderFactory;
import javax.xml.parsers.ParserConfigurationException;
import java.io.File;
import java.io.IOException;

/**
 * Loads XML configuration files.
 *
 * The parser is hardened against XXE: DOCTYPE declarations are rejected outright,
 * external general/parameter entities and external DTD loading are disabled,
 * XInclude and entity expansion are off, and secure processing is enabled.
 */
public class ConfigService {

    public Document loadConfig(String configPath) throws Exception {
        if (configPath == null || configPath.trim().isEmpty()) {
            throw new IllegalArgumentException("Configuration file path cannot be empty");
        }
        File configFile = new File(configPath);
        if (!configFile.isFile()) {
            throw new IOException("Configuration file does not exist or is not a file: " + configPath);
        }

        try {
            DocumentBuilder builder = newSecureFactory().newDocumentBuilder();
            builder.setEntityResolver((publicId, systemId) -> {
                throw new SAXException("External entities are not allowed: " + systemId);
            });
            return builder.parse(configFile);
        } catch (ParserConfigurationException e) {
            throw new Exception("XML parser configuration error: " + e.getMessage(), e);
        }
    }

    private static DocumentBuilderFactory newSecureFactory() throws ParserConfigurationException {
        DocumentBuilderFactory factory = DocumentBuilderFactory.newInstance();
        factory.setFeature(XMLConstants.FEATURE_SECURE_PROCESSING, true);
        factory.setFeature("http://apache.org/xml/features/disallow-doctype-decl", true);
        factory.setFeature("http://xml.org/sax/features/external-general-entities", false);
        factory.setFeature("http://xml.org/sax/features/external-parameter-entities", false);
        factory.setFeature("http://apache.org/xml/features/nonvalidating/load-external-dtd", false);
        factory.setAttribute(XMLConstants.ACCESS_EXTERNAL_DTD, "");
        factory.setAttribute(XMLConstants.ACCESS_EXTERNAL_SCHEMA, "");
        factory.setXIncludeAware(false);
        factory.setExpandEntityReferences(false);
        return factory;
    }
}
