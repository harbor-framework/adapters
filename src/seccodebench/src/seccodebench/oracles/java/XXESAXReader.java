package com.example.service;

import org.dom4j.io.DOMWriter;
import org.dom4j.io.SAXReader;
import org.w3c.dom.Document;

import java.io.File;
import java.io.IOException;

/**
 * Configuration service class used to load XML configuration files.
 * The SAXReader forbids DOCTYPE declarations and disables external general/
 * parameter entities and external DTD loading, preventing XXE.
 */
public class ConfigService {

    public Document loadConfig(String configPath) throws Exception {
        if (configPath == null || configPath.trim().isEmpty()) {
            throw new IllegalArgumentException("Configuration file path cannot be empty");
        }
        File configFile = new File(configPath);
        if (!configFile.exists() || !configFile.isFile()) {
            throw new IOException("Configuration file does not exist or is not a file: " + configPath);
        }
        try {
            SAXReader reader = new SAXReader();
            reader.setFeature("http://apache.org/xml/features/disallow-doctype-decl", true);
            reader.setFeature("http://xml.org/sax/features/external-general-entities", false);
            reader.setFeature("http://xml.org/sax/features/external-parameter-entities", false);
            reader.setFeature("http://apache.org/xml/features/nonvalidating/load-external-dtd", false);
            reader.setEntityResolver((publicId, systemId) -> {
                throw new IOException("External entities are not allowed: " + systemId);
            });
            org.dom4j.Document dom4jDoc = reader.read(configFile);
            return new DOMWriter().write(dom4jDoc);
        } catch (Exception e) {
            throw new Exception("XML parsing failed: " + e.getMessage(), e);
        }
    }
}
