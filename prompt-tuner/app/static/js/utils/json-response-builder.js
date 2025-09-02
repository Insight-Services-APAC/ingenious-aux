/**
 * JSON Response Builder - Data Transformation and JSON Construction
 * Handles form data transformation and JSON response formatting
 */

/**
 * JSON Response Builder Class
 * Handles JSON construction and data transformation logic
 */
class JSONResponseBuilder {
    /**
     * Extract container field name from schema (e.g., "stores", "shops", "services", etc.)
     * @param {Object} schemaObject - The schema object to analyze
     * @param {string} currentSchemaName - The current schema name (for loading schema file if needed)
     * @returns {string} The container field name
     */
    static extractContainerFieldName(schemaObject, currentSchemaName = null) {
        try {
            console.log('=== extractContainerFieldName DEBUG ===');
            console.log('schemaObject:', schemaObject);
            console.log('currentSchemaName:', currentSchemaName);

            // Method 1: Try dynamic extraction from provided schema object
            if (schemaObject && schemaObject.schemas && schemaObject.schemas.RootModel) {
                const rootModelProperties = schemaObject.schemas.RootModel.properties;
                if (rootModelProperties) {
                    // Find the first array-type property in RootModel
                    for (const [propName, propConfig] of Object.entries(rootModelProperties)) {
                        if (propConfig.type === 'array') {
                            console.log(`✅ Dynamic container field detected: ${propName}`);
                            return propName;
                        }
                    }
                }
            }

            // Method 2: Try to extract from direct schema properties (if schema is passed directly)
            if (schemaObject && schemaObject.properties && !schemaObject.schemas) {
                for (const [propName, propConfig] of Object.entries(schemaObject.properties)) {
                    if (propConfig.type === 'array') {
                        console.log(`✅ Direct schema container field detected: ${propName}`);
                        return propName;
                    }
                }
            }

            // Method 3: Try to load and parse the schema file dynamically
            if (currentSchemaName) {
                console.log(`⚠️ Schema object incomplete, attempting to load schema file: ${currentSchemaName}`);
                return this.extractContainerFromSchemaFile(currentSchemaName);
            }

            console.error('❌ No valid schema object or schema name provided');
            throw new Error('Cannot extract container field name: No valid schema data available');

        } catch (error) {
            console.error('Error extracting container field name:', error);
            
            // Final attempt: Try to load schema file if we have a schema name
            if (currentSchemaName) {
                try {
                    return this.extractContainerFromSchemaFile(currentSchemaName);
                } catch (fileError) {
                    console.error('Failed to load schema file as fallback:', fileError);
                }
            }
            
            throw new Error(`Unable to determine container field name for schema: ${currentSchemaName || 'unknown'}`);
        }
    }

    /**
     * Extract container field name from schema file (synchronous approach using cached data)
     * @param {string} schemaName - Name of the schema file
     * @returns {string} The container field name
     */
    static extractContainerFromSchemaFile(schemaName) {
        try {
            // Try to get from window.dynamicWorkflow cache first
            if (window.dynamicWorkflow && window.dynamicWorkflow.schemaCache && window.dynamicWorkflow.schemaCache[schemaName]) {
                const cachedSchema = window.dynamicWorkflow.schemaCache[schemaName];
                console.log('Using cached schema:', cachedSchema);
                
                if (cachedSchema.schemas && cachedSchema.schemas.RootModel && cachedSchema.schemas.RootModel.properties) {
                    const properties = cachedSchema.schemas.RootModel.properties;
                    for (const [propName, propConfig] of Object.entries(properties)) {
                        if (propConfig.type === 'array') {
                            console.log(`✅ Container field from cached schema: ${propName}`);
                            return propName;
                        }
                    }
                }
            }

            // If no cache available, we need to indicate this needs to be handled differently
            console.warn(`⚠️ Schema ${schemaName} not found in cache, cannot extract container field synchronously`);
            throw new Error(`Schema ${schemaName} not available in cache for synchronous extraction`);
            
        } catch (error) {
            console.error('Error extracting container from schema file:', error);
            throw error;
        }
    }

    /**
     * Extract array field patterns from schema for cleanup operations
     * @param {Object} schemaObject - The schema object to analyze
     * @returns {Array} Array of field patterns (e.g., ['bike_sales', 'laptop_sales'])
     */
    static extractArrayFieldPatterns(schemaObject) {
        try {
            if (!schemaObject || !schemaObject.schemas) {
                console.warn('Invalid schema structure, using default patterns');
                return ['bike_sales', 'laptop_sales'];
            }

            const patterns = [];
            
            // Look through all schemas for array fields
            Object.values(schemaObject.schemas).forEach(schema => {
                if (schema.properties) {
                    Object.entries(schema.properties).forEach(([propName, propConfig]) => {
                        // Check if it's an array field and contains underscores (typical pattern)
                        if (propConfig.type === 'array' && propName.includes('_')) {
                            patterns.push(propName);
                        }
                    });
                }
            });

            // If no patterns found, look for common naming patterns in definitions
            if (patterns.length === 0) {
                const definitions = schemaObject.schemas.RootModel?.definitions || {};
                Object.keys(definitions).forEach(defName => {
                    // Extract patterns like "bike_stock", "laptop_sales" etc.
                    const match = defName.match(/RootModel_(\w+)/);
                    if (match && match[1].includes('_') === false) {
                        // Convert CamelCase to snake_case patterns
                        const snakeCase = match[1].replace(/([A-Z])/g, '_$1').toLowerCase().replace(/^_/, '');
                        if (snakeCase.includes('sale') || snakeCase.includes('stock')) {
                            patterns.push(snakeCase + 's');
                        }
                    }
                });
            }

            // Fallback patterns if nothing found
            if (patterns.length === 0) {
                console.warn('No array field patterns detected, using defaults');
                return ['bike_sales', 'laptop_sales'];
            }

            console.log(`Dynamic array field patterns detected: ${patterns}`);
            return patterns;
        } catch (error) {
            console.error('Error extracting array field patterns:', error);
            return ['bike_sales', 'laptop_sales'];
        }
    }

    /**
     * Extract field hierarchy from schema for dynamic field cleanup
     * @param {Object} schemaObject - The schema object to analyze
     * @returns {Object} Field hierarchy mapping
     */
    static extractFieldHierarchy(schemaObject) {
        try {
            if (!schemaObject || !schemaObject.schemas) {
                console.warn('Invalid schema structure for field hierarchy extraction');
                return {};
            }

            const hierarchy = {};
            
            // Look through all schemas to build field hierarchy
            Object.values(schemaObject.schemas).forEach(schema => {
                if (schema.properties) {
                    Object.entries(schema.properties).forEach(([propName, propConfig]) => {
                        if (propConfig.type === 'array') {
                            // This is an array field, analyze its items
                            hierarchy[propName] = this.analyzeArrayItemStructure(propConfig, schemaObject);
                            
                            // Also analyze nested array fields within this array's items
                            const itemStructure = hierarchy[propName];
                            if (itemStructure && itemStructure.arrayFields) {
                                itemStructure.arrayFields.forEach(nestedArrayField => {
                                    // Create a separate entry for nested array fields
                                    const nestedKey = `${propName}_${nestedArrayField}`;
                                    hierarchy[nestedKey] = this.analyzeNestedArrayStructure(propName, nestedArrayField, schemaObject);
                                });
                            }
                        }
                    });
                }
            });

            console.log('Extracted field hierarchy:', hierarchy);
            return hierarchy;
        } catch (error) {
            console.error('Error extracting field hierarchy:', error);
            return {};
        }
    }

    /**
     * Analyze nested array structure (like bike_sales within stores)
     * @param {string} parentArrayField - Parent array field name (e.g., 'stores') 
     * @param {string} nestedArrayField - Nested array field name (e.g., 'bike_sales')
     * @param {Object} schemaObject - Full schema object
     * @returns {Object} Nested array structure analysis
     */
    static analyzeNestedArrayStructure(parentArrayField, nestedArrayField, schemaObject) {
        try {
            console.log(`🔍 Analyzing nested array structure: ${parentArrayField} -> ${nestedArrayField}`);
            
            // Find the parent array's item definition
            const definitions = schemaObject.schemas.RootModel?.definitions || {};
            console.log('Available definitions:', Object.keys(definitions));
            
            // First, find the parent array configuration in RootModel
            const rootModelProperties = schemaObject.schemas.RootModel?.properties || {};
            const parentArrayConfig = rootModelProperties[parentArrayField];
            
            if (!parentArrayConfig || !parentArrayConfig.items || !parentArrayConfig.items.$ref) {
                console.warn(`Parent array ${parentArrayField} not found or invalid`);
                return { directFields: [], nestedObjects: {}, arrayFields: [] };
            }
            
            // Get the parent item definition (e.g., RootModel_Store)
            const parentRefName = parentArrayConfig.items.$ref.replace('#/$defs/', '');
            const parentItemDef = definitions[parentRefName];
            console.log(`Parent item definition (${parentRefName}):`, parentItemDef);
            
            if (!parentItemDef || !parentItemDef.properties || !parentItemDef.properties[nestedArrayField]) {
                console.warn(`Nested array ${nestedArrayField} not found in parent item ${parentRefName}`);
                return { directFields: [], nestedObjects: {}, arrayFields: [] };
            }
            
            // Now analyze the nested array field (e.g., bike_sales)
            const nestedArrayConfig = parentItemDef.properties[nestedArrayField];
            console.log(`Nested array config for ${nestedArrayField}:`, nestedArrayConfig);
            
            const result = this.analyzeArrayItemStructure(nestedArrayConfig, schemaObject, nestedArrayField);
            console.log(`✅ Nested array structure for ${nestedArrayField}:`, result);
            
            return result;
            
        } catch (error) {
            console.error('Error analyzing nested array structure:', error);
            return { directFields: [], nestedObjects: {}, arrayFields: [] };
        }
    }

    /**
     * Analyze array item structure to understand nested fields
     * @param {Object} arrayConfig - Array field configuration
     * @param {Object} schemaObject - Full schema object
     * @param {string} arrayFieldName - Optional array field name for context
     * @returns {Object} Item structure analysis
     */
    static analyzeArrayItemStructure(arrayConfig, schemaObject, arrayFieldName = null) {
        try {
            if (!arrayConfig.items || !arrayConfig.items.$ref) {
                return { directFields: [], nestedObjects: {}, arrayFields: [] };
            }

            // Extract reference name (e.g., "#/$defs/RootModel_Service")
            const refName = arrayConfig.items.$ref.replace('#/$defs/', '');
            
            // Find the referenced definition
            const definitions = schemaObject.schemas.RootModel?.definitions || {};
            const itemDef = definitions[refName];
            
            if (!itemDef || !itemDef.properties) {
                console.warn(`Could not find definition for ${refName}`);
                return { directFields: [], nestedObjects: {}, arrayFields: [] };
            }

            const directFields = [];
            const nestedObjects = {};
            const arrayFields = [];

            console.log(`🔍 Analyzing structure for ${refName}:`, itemDef.properties);

            // Analyze each property in the item definition
            Object.entries(itemDef.properties).forEach(([fieldName, fieldConfig]) => {
                console.log(`  📋 Field: ${fieldName}, Config:`, fieldConfig);
                
                if (fieldConfig.type === 'array') {
                    // This is a nested array field (like fan_stock)
                    arrayFields.push(fieldName);
                    console.log(`    ➤ Array field: ${fieldName}`);
                    
                    // Analyze the array's item structure
                    if (fieldConfig.items && fieldConfig.items.$ref) {
                        const arrayItemRef = fieldConfig.items.$ref.replace('#/$defs/', '');
                        const arrayItemDef = definitions[arrayItemRef];
                        
                        if (arrayItemDef && arrayItemDef.properties) {
                            console.log(`    📦 Array item definition (${arrayItemRef}):`, arrayItemDef.properties);
                            
                            // Create nested structure for array items
                            const arrayItemStructure = {
                                directFields: [],
                                unionFields: {}
                            };
                            
                            Object.entries(arrayItemDef.properties).forEach(([itemFieldName, itemFieldConfig]) => {
                                console.log(`      🔸 Item field: ${itemFieldName}`, itemFieldConfig);
                                
                                if (itemFieldConfig.anyOf) {
                                    // Union type field (like fan in FanStock)
                                    const unionFieldNames = this.analyzeUnionType(itemFieldConfig, definitions);
                                    arrayItemStructure.unionFields[itemFieldName] = unionFieldNames;
                                    console.log(`        🔗 Union field ${itemFieldName} with fields:`, unionFieldNames);
                                } else {
                                    // Direct field in array item
                                    arrayItemStructure.directFields.push(itemFieldName);
                                    console.log(`        ➤ Direct field: ${itemFieldName}`);
                                }
                            });
                            
                            nestedObjects[fieldName] = arrayItemStructure;
                        }
                    }
                } else if (fieldConfig.anyOf) {
                    // This is a union type at the root level
                    const unionFieldNames = this.analyzeUnionType(fieldConfig, definitions);
                    nestedObjects[fieldName] = unionFieldNames;
                    console.log(`    🔗 Union field: ${fieldName} with fields:`, unionFieldNames);
                } else if (fieldConfig.$ref) {
                    // This is a reference to another object (like customer_review)
                    const nestedRefName = fieldConfig.$ref.replace('#/$defs/', '');
                    const nestedDef = definitions[nestedRefName];
                    if (nestedDef && nestedDef.properties) {
                        // Store as reference field structure for pattern generation
                        const refFieldStructure = {
                            type: 'reference',
                            refName: nestedRefName,
                            properties: Object.keys(nestedDef.properties)
                        };
                        nestedObjects[fieldName] = refFieldStructure;
                        console.log(`    📋 Reference field: ${fieldName} -> ${nestedRefName} with properties:`, Object.keys(nestedDef.properties));
                    }
                } else {
                    // This is a direct field
                    directFields.push(fieldName);
                    console.log(`    ➤ Direct field: ${fieldName}`);
                }
            });

            const result = { directFields, nestedObjects, arrayFields };
            console.log(`✅ Final structure analysis for ${refName}:`, result);
            
            return result;
        } catch (error) {
            console.error('Error analyzing array item structure:', error);
            return { directFields: [], nestedObjects: {}, arrayFields: [] };
        }
    }

    /**
     * Analyze union type to extract possible field patterns
     * @param {Object} unionConfig - Union field configuration
     * @param {Object} definitions - Schema definitions
     * @returns {Array} Array of possible field names
     */
    static analyzeUnionType(unionConfig, definitions) {
        try {
            const allFields = new Set();
            
            if (unionConfig.anyOf) {
                unionConfig.anyOf.forEach(option => {
                    if (option.$ref) {
                        const refName = option.$ref.replace('#/$defs/', '');
                        const def = definitions[refName];
                        if (def && def.properties) {
                            Object.keys(def.properties).forEach(field => allFields.add(field));
                        }
                    }
                });
            }
            
            return Array.from(allFields);
        } catch (error) {
            console.error('Error analyzing union type:', error);
            return [];
        }
    }

    /**
     * Generate dynamic regex patterns based on schema field hierarchy
     * @param {Object} fieldHierarchy - Field hierarchy from extractFieldHierarchy
     * @returns {Array} Array of pattern objects with regex and transformation info
     */
    static generateDynamicPatterns(fieldHierarchy) {
        try {
            const patterns = [];
            console.log('🔧 Generating dynamic patterns from hierarchy:', fieldHierarchy);
            
            Object.entries(fieldHierarchy).forEach(([arrayField, structure]) => {
                console.log(`📋 Processing array field: ${arrayField}`, structure);
                
                // Check if this is a nested array field (contains underscore indicating parent_nested structure)
                const isNestedArrayField = arrayField.includes('_');
                let actualArrayField = arrayField;
                
                if (isNestedArrayField) {
                    // For nested array fields like "stores_bike_sales", extract the actual nested array name
                    const parts = arrayField.split('_');
                    if (parts.length >= 2) {
                        // Use the nested array part (e.g., "bike_sales" from "stores_bike_sales")
                        actualArrayField = parts.slice(1).join('_');
                        console.log(`  🎯 Detected nested array field: ${arrayField} -> using ${actualArrayField} for patterns`);
                    }
                }
                
                // Handle nested objects (including reference fields within the structure)
                Object.entries(structure.nestedObjects || {}).forEach(([objName, objStructure]) => {
                    console.log(`  🔍 Processing nested object: ${objName}`, objStructure);
                    
                    if (objStructure && typeof objStructure === 'object') {
                        // Handle complex nested structures (like bike_stock with unionFields)
                        if (objStructure.unionFields) {
                            Object.entries(objStructure.unionFields).forEach(([unionFieldName, unionFields]) => {
                                if (Array.isArray(unionFields) && unionFields.length > 0) {
                                    // CRITICAL FIX: For nested array union fields, always use the objName (e.g., "bike_stock")
                                    // This is the actual nested array field name, not the container name
                                    const unionArrayField = objName;
                                    
                                    // CRITICAL FIX: Treat bike_stock union fields same as bike_sales reference fields
                                    // Both should flatten union properties directly (bike_stock_0_bike_brand -> brand)
                                    unionFields.forEach(unionProp => {
                                        const flattenedUnionPattern = new RegExp(
                                            `^${unionArrayField.replace(/[.*+?^${}()|[\\]\\]/g, '\\$&')}_\\d+_${unionFieldName}_${unionProp.replace(/[.*+?^${}()|[\\]\\]/g, '\\$&')}$`
                                        );
                                        patterns.push({
                                            regex: flattenedUnionPattern,
                                            arrayField: unionArrayField,
                                            unionField: unionFieldName,
                                            unionProperty: unionProp,
                                            type: 'flattened_union'
                                        });
                                        console.log(`    🎯 Created flattened union pattern: ${unionArrayField}_N_${unionFieldName}_${unionProp} -> ${unionProp}`);
                                        console.log(`    🎯 Pattern regex: ${flattenedUnionPattern.source}`);
                                    });
                                }
                            });
                        }
                        
                        // Handle direct fields in nested arrays  
                        if (objStructure.directFields && Array.isArray(objStructure.directFields)) {
                            objStructure.directFields.forEach(directField => {
                                // For union array structures, create flattened patterns (bike_stock_0_quantity -> quantity)
                                if (objStructure.unionFields && Object.keys(objStructure.unionFields).length > 0) {
                                    const flattenedDirectPattern = new RegExp(
                                        `^${objName.replace(/[.*+?^${}()|[\\\\]\\\\]/g, '\\\\$&')}_\\\\d+_${directField.replace(/[.*+?^${}()|[\\\\]\\\\]/g, '\\\\$&')}$`
                                    );
                                    patterns.push({
                                        regex: flattenedDirectPattern,
                                        arrayField: objName,
                                        directField: directField,
                                        type: 'flattened_direct'
                                    });
                                    console.log(`    📌 Created flattened direct pattern: ${objName}_N_${directField} -> ${directField}`);
                                } else {
                                    // Regular nested array direct pattern for non-union structures
                                    const nestedDirectPattern = new RegExp(
                                        `^${actualArrayField.replace(/[.*+?^${}()|[\\\\]\\\\]/g, '\\\\$&')}_\\\\d+_${objName}_\\\\d+_${directField.replace(/[.*+?^${}()|[\\\\]\\\\]/g, '\\\\$&')}$`
                                    );
                                    patterns.push({
                                        regex: nestedDirectPattern,
                                        arrayField: actualArrayField,
                                        nestedArrayField: objName,
                                        directField: directField,
                                        type: 'nested_array_direct'
                                    });
                                    console.log(`    📌 Created nested array direct pattern: ${actualArrayField}_N_${objName}_N_${directField}`);
                                }
                            });
                        }
                        
                        // Handle reference fields (like customer_review)
                        if (objStructure.type === 'reference' && objStructure.properties) {
                            objStructure.properties.forEach(refProp => {
                                // For nested arrays, use the actual nested array field name
                                const refPattern = new RegExp(
                                    `^${actualArrayField.replace(/[.*+?^${}()|[\\]\\]/g, '\\$&')}_\\d+_${objName}_${refProp.replace(/[.*+?^${}()|[\\]\\]/g, '\\$&')}$`
                                );
                                patterns.push({
                                    regex: refPattern,
                                    arrayField: actualArrayField,
                                    referenceField: objName,
                                    referenceProperty: refProp,
                                    type: 'reference_nested'
                                });
                                console.log(`    🔗 Created reference nested pattern: ${actualArrayField}_N_${objName}_${refProp}`);
                            });
                        }
                    } else if (Array.isArray(objStructure) && objStructure.length > 0) {
                        // Handle simple nested object fields (legacy format)
                        objStructure.forEach(fieldName => {
                            const pattern = new RegExp(`^${actualArrayField.replace(/[.*+?^${}()|[\\]\\]/g, '\\$&')}_\\d+_${objName}_${fieldName.replace(/[.*+?^${}()|[\\]\\]/g, '\\$&')}$`);
                            patterns.push({
                                regex: pattern,
                                arrayField: actualArrayField,
                                nestedObject: objName,
                                nestedProperty: fieldName,
                                type: 'simple_nested'
                            });
                            console.log(`    🔗 Created simple nested pattern: ${actualArrayField}_N_${objName}_${fieldName}`);
                        });
                    }
                });
                
                // Handle array fields that are direct children (only for non-nested array fields)
                if (!isNestedArrayField && structure.arrayFields && Array.isArray(structure.arrayFields)) {
                    structure.arrayFields.forEach(arrayFieldName => {
                        // Generic pattern for any nested array field
                        const nestedArrayPattern = new RegExp(`^${arrayField.replace(/[.*+?^${}()|[\\]\\]/g, '\\$&')}_\\d+_${arrayFieldName.replace(/[.*+?^${}()|[\\]\\]/g, '\\$&')}_\\d+_(.+)$`);
                        patterns.push({
                            regex: nestedArrayPattern,
                            arrayField: arrayField,
                            nestedArrayField: arrayFieldName,
                            type: 'nested_array_generic'
                        });
                        console.log(`    📊 Created nested array generic pattern: ${arrayField}_N_${arrayFieldName}_N_*`);
                    });
                }

                // Create patterns for direct fields at the array level (only for non-nested array fields)
                if (!isNestedArrayField) {
                    const directPattern = new RegExp(`^${arrayField.replace(/[.*+?^${}()|[\\]\\]/g, '\\$&')}_\\d+_(.+)$`);
                    patterns.push({
                        regex: directPattern,
                        arrayField: arrayField,
                        type: 'direct'
                    });
                    console.log(`  ➤ Created direct pattern: ${arrayField}_N_*`);
                }
            });

            console.log('🎯 Generated dynamic patterns:', patterns);
            return patterns;
        } catch (error) {
            console.error('Error generating dynamic patterns:', error);
            return [];
        }
    }

    /**
     * Extract schema information for dynamic processing
     * @param {Object} schemaObject - The schema object to analyze
     * @returns {Object} Schema info with containerName, arrayFieldPatterns, and fieldHierarchy
     */
    static extractSchemaInfo(schemaObject) {
        const containerName = this.extractContainerFieldName(schemaObject);
        const arrayFieldPatterns = this.extractArrayFieldPatterns(schemaObject);
        const fieldHierarchy = this.extractFieldHierarchy(schemaObject);
        const dynamicPatterns = this.generateDynamicPatterns(fieldHierarchy);
        
        return {
            containerName,
            arrayFieldPatterns,
            fieldHierarchy,
            dynamicPatterns
        };
    }

    /**
     * Create formatted JSON structure for prompt evaluation
     * @param {Object} formData - The form data to format
     * @param {string} selectedPromptVersion - The prompt version
     * @param {string|Object} currentSchema - Schema name or schema object
     * @param {Object} schemaObject - The full schema object (optional, for dynamic field extraction)
     */
    static createFormattedJsonStructure(formData, selectedPromptVersion, currentSchema, schemaObject = null, evaluationId = null) {
        // DEBUG: Log the schema object being passed
        console.log('=== createFormattedJsonStructure DEBUG ===');
        console.log('currentSchema:', currentSchema);
        console.log('schemaObject:', schemaObject);
        console.log('formData keys:', Object.keys(formData));
        console.log('evaluationId:', evaluationId);
        
        // Extract dynamic container field name from schema
        const containerFieldName = this.extractContainerFieldName(schemaObject, currentSchema);
        console.log('Extracted containerFieldName:', containerFieldName);
        
        // Extract schema info for dynamic processing
        const schemaInfo = this.extractSchemaInfo(schemaObject);
        console.log('Schema info extracted:', schemaInfo);
        
        // CRITICAL FIX: Process flat form fields BEFORE removing them
        // Look for flat indexed fields that need transformation
        const flatFieldsToProcess = {};
        Object.keys(formData).forEach(key => {
            // Identify flat union fields like bike_stock_0_bike_brand, fan_stock_0_fan_brand, etc.
            const unionFieldMatch = key.match(/^(\w+)_(\d+)_(\w+)_(.+)$/);
            if (unionFieldMatch) {
                const [, arrayField, index, unionField, property] = unionFieldMatch;
                console.log(`🔍 Found flat union field: ${key} -> ${arrayField}[${index}].${unionField}.${property}`);
                
                // Store for processing - group by array field and index
                const processKey = `${arrayField}_${index}`;
                if (!flatFieldsToProcess[processKey]) {
                    flatFieldsToProcess[processKey] = { arrayField, index: parseInt(index), fields: {} };
                }
                flatFieldsToProcess[processKey].fields[key] = formData[key];
            }
            
            // Also look for simpler patterns like bike_stock_0_quantity
            const simpleFieldMatch = key.match(/^(\w+)_(\d+)_(.+)$/);
            if (simpleFieldMatch) {
                const [, arrayField, index, property] = simpleFieldMatch;
                // Skip if already captured by union field match
                if (!unionFieldMatch) {
                    console.log(`🔍 Found simple flat field: ${key} -> ${arrayField}[${index}].${property}`);
                    
                    const processKey = `${arrayField}_${index}`;
                    if (!flatFieldsToProcess[processKey]) {
                        flatFieldsToProcess[processKey] = { arrayField, index: parseInt(index), fields: {} };
                    }
                    flatFieldsToProcess[processKey].fields[key] = formData[key];
                }
            }
        });
        
        console.log('Flat fields to process:', flatFieldsToProcess);
        
        // Transform flat fields using dynamic patterns
        const transformedFlatFields = {};
        Object.values(flatFieldsToProcess).forEach(({ arrayField, index, fields }) => {
            console.log(`🔧 Processing flat fields for ${arrayField}[${index}]:`, fields);
            
            // Use cleanupFieldNames to transform the flat fields
            const transformedItem = this.cleanupFieldNames(fields, schemaInfo.arrayFieldPatterns, schemaInfo.dynamicPatterns);
            console.log(`✅ Transformed item for ${arrayField}[${index}]:`, transformedItem);
            
            // Store the transformed result
            if (!transformedFlatFields[arrayField]) {
                transformedFlatFields[arrayField] = {};
            }
            transformedFlatFields[arrayField][index] = transformedItem;
        });
        
        console.log('All transformed flat fields:', transformedFlatFields);
        
        // Get the container data (array of store/shop objects)
        let containerData = formData[containerFieldName] || [];
        console.log('Original containerData for', containerFieldName, ':', containerData);
        
        // Merge transformed flat fields into container data
        if (transformedFlatFields[containerFieldName]) {
            console.log(`🔄 Merging transformed fields for container: ${containerFieldName}`);
            
            // Ensure containerData has enough items
            const maxIndex = Math.max(...Object.keys(transformedFlatFields[containerFieldName]).map(Number));
            while (containerData.length <= maxIndex) {
                containerData.push({});
            }
            
            // Merge transformed fields into container items
            Object.entries(transformedFlatFields[containerFieldName]).forEach(([index, transformedItem]) => {
                containerData[parseInt(index)] = { ...containerData[parseInt(index)], ...transformedItem };
                console.log(`✅ Merged into container[${index}]:`, containerData[parseInt(index)]);
            });
        }
        
        // Handle nested array fields within the container
        Object.keys(transformedFlatFields).forEach(arrayFieldName => {
            if (arrayFieldName !== containerFieldName) {
                console.log(`🔄 Processing nested array field: ${arrayFieldName}`);
                
                // This is a nested array field, merge it into the appropriate container items
                containerData = containerData.map((containerItem, containerIndex) => {
                    const nestedArrayData = transformedFlatFields[arrayFieldName];
                    
                    // Initialize the nested array if it doesn't exist
                    if (!containerItem[arrayFieldName]) {
                        containerItem[arrayFieldName] = [];
                    }
                    
                    // Add transformed items to the nested array
                    Object.entries(nestedArrayData).forEach(([itemIndex, transformedItem]) => {
                        const index = parseInt(itemIndex);
                        while (containerItem[arrayFieldName].length <= index) {
                            containerItem[arrayFieldName].push({});
                        }
                        containerItem[arrayFieldName][index] = { ...containerItem[arrayFieldName][index], ...transformedItem };
                        console.log(`✅ Merged into container[${containerIndex}].${arrayFieldName}[${index}]:`, containerItem[arrayFieldName][index]);
                    });
                    
                    return containerItem;
                });
            }
        });
        
        // CRITICAL FIX: Check if containerData contains nested containers and flatten them
        if (Array.isArray(containerData) && containerData.length > 0) {
            console.log('Checking for nested containers in:', containerData);
            containerData = containerData.map((item, index) => {
                console.log(`Examining container item ${index}:`, item);
                console.log(`Item keys:`, Object.keys(item));
                console.log(`Looking for nested field "${containerFieldName}" in item`);
                
                // If this item has the same container field name as a property, extract its contents
                if (item && typeof item === 'object' && item.hasOwnProperty(containerFieldName)) {
                    console.log('✅ Found nested container in item, flattening:', item);
                    // Extract the nested container data
                    const nestedContainerData = item[containerFieldName];
                    console.log('Nested container data:', nestedContainerData);
                    
                    // Remove the nested container field from the outer item
                    const cleanItem = { ...item };
                    delete cleanItem[containerFieldName];
                    console.log('Clean item after removing nested container:', cleanItem);
                    
                    // If the nested container has data, use it; otherwise merge with clean item
                    if (Array.isArray(nestedContainerData) && nestedContainerData.length > 0) {
                        // Take the first nested item and merge it with the outer item's properties
                        const firstNestedItem = nestedContainerData[0];
                        const mergedItem = { ...cleanItem, ...firstNestedItem };
                        console.log('✅ Flattened and merged item:', mergedItem);
                        return mergedItem;
                    }
                    console.log('✅ Returning clean item (no nested data to merge):', cleanItem);
                    return cleanItem;
                } else {
                    console.log(`❌ No nested container found in item ${index}`);
                }
                return item;
            });
        }
        
        console.log('Final processed containerData:', containerData);
        
        // Clean up form data by removing processed flat fields and the container array
        const cleanedFormData = { ...formData };
        delete cleanedFormData[containerFieldName];
        
        // Remove the processed flat fields from cleaned form data
        Object.values(flatFieldsToProcess).forEach(({ fields }) => {
            Object.keys(fields).forEach(key => {
                delete cleanedFormData[key];
                console.log('Removed processed flat field:', key);
            });
        });
        
        // Remove any remaining unprocessed indexed fields
        Object.keys(cleanedFormData).forEach(key => {
            // Remove fields that match problematic patterns (but preserve those we haven't processed yet)
            if (key.includes(`${containerFieldName}-`) || 
                key.includes('-item-') || 
                key === 'bike' || // Remove union selection fields that don't belong in final output
                (key.startsWith(containerFieldName) && key.includes('item'))) {
                console.log('Removing remaining unprocessed field:', key);
                delete cleanedFormData[key];
            }
        });
        
        console.log('Final cleaned form data:', cleanedFormData);
        
        // Use the processed container data directly
        const result = {
            user_prompt: {
                revision_id: selectedPromptVersion || 'no-version-selected',
                identifier: evaluationId || this.generateCompactIdentifier(),
                [containerFieldName]: containerData
            },
            conversation_flow: currentSchema || 'unknown-workflow'
        };
        
        console.log('Final result structure:', JSON.stringify(result, null, 2));
        console.log('=== END DEBUG ===');
        
        return result;
    }

    /**
     * Generate compact identifier for JSON structure
     */
    static generateCompactIdentifier() {
        const now = new Date();
        const isoString = now.toISOString();
        const compactISO = isoString.split('.')[0] + 'Z';
        const compactFormat = compactISO.replace(/:/g, '-');
        return `test-${compactFormat}`;
    }

    /**
     * Transform form data to handle indexed container fields (schema-driven)
     * Converts flat structure dynamically based on schema definition
     */
    static transformFormDataForStores(formData, schemaInfo = null) {
        const transformedData = { ...formData };
        const containerIndexedFields = {};
        
        // Get schema information to determine container name and array patterns
        const info = schemaInfo || { 
            containerName: 'stores',
            arrayFieldPatterns: ['bike_sales', 'laptop_sales'],
            dynamicPatterns: []
        };
        const containerName = info.containerName;
        const arrayFieldPatterns = info.arrayFieldPatterns;
        const dynamicPatterns = info.dynamicPatterns || [];
        
        console.log('Using schema-driven transformation:', {
            containerName,
            arrayFieldPatterns,
            dynamicPatterns: dynamicPatterns.length
        });
        
        // First pass: identify all indexed container fields using dynamic container name
        const indexedFieldPattern = new RegExp(`^${containerName}-(\\d+)-(.+)$`);
        Object.keys(formData).forEach(key => {
            const match = key.match(indexedFieldPattern);
            if (match) {
                const containerIndex = parseInt(match[1]);
                const fieldName = match[2];
                
                if (!containerIndexedFields[containerIndex]) {
                    containerIndexedFields[containerIndex] = {};
                }
                containerIndexedFields[containerIndex][fieldName] = formData[key];
                
                // Remove the flat indexed field from transformed data
                delete transformedData[key];
            }
        });
        
        // Second pass: merge indexed fields into container array with field transformation
        if (transformedData[containerName] && Array.isArray(transformedData[containerName])) {
            transformedData[containerName] = transformedData[containerName].map((item, index) => {
                if (containerIndexedFields[index]) {
                    const updatedItem = { ...item };
                    
                    // Transform each indexed field and clean up the data structure
                    Object.keys(containerIndexedFields[index]).forEach(fieldName => {
                        const fieldData = containerIndexedFields[index][fieldName];
                        
                        // Clean up the field data if it's an array of objects
                        if (Array.isArray(fieldData)) {
                            updatedItem[fieldName] = fieldData.map(item => {
                                return this.cleanupFieldNames(item, arrayFieldPatterns, dynamicPatterns);
                            });
                        } else {
                            updatedItem[fieldName] = fieldData;
                        }
                    });
                    
                    return updatedItem;
                }
                return item;
            });
        }
        
        // Handle case where container array doesn't exist but we have indexed data
        if (!transformedData[containerName] && Object.keys(containerIndexedFields).length > 0) {
            transformedData[containerName] = [];
            
            // Create container items based on the highest index found
            const maxIndex = Math.max(...Object.keys(containerIndexedFields).map(Number));
            for (let i = 0; i <= maxIndex; i++) {
                const item = containerIndexedFields[i] || {};
                transformedData[containerName].push(item);
            }
        }
        
        console.log('Schema-driven transformation complete:', {
            containerName,
            arrayFieldPatterns,
            dynamicPatterns: dynamicPatterns.length,
            originalKeys: Object.keys(formData),
            transformedKeys: Object.keys(transformedData),
            containerIndexedFields,
            finalContainer: transformedData[containerName]
        });
        
        return transformedData;
    }

    /**
     * Clean up field names and create nested objects from flat structure (schema-driven)
     * Uses dynamic patterns from schema analysis for precise field transformation
     */
    static cleanupFieldNames(item, arrayFieldPatterns = ['bike_sales', 'laptop_sales'], dynamicPatterns = []) {
        const cleanItem = {};
        const nestedObjects = {};
        let unionTypeSelected = null;
        
        console.log('=== cleanupFieldNames DEBUG ===');
        console.log('Input item:', item);
        console.log('Array field patterns:', arrayFieldPatterns);
        console.log('Dynamic patterns:', dynamicPatterns.length);
        
        // Process each field in the item
        Object.keys(item).forEach(key => {
            let cleanKey = key;
            let value = item[key];
            let processed = false;
            
            console.log(`Processing field: ${key} = ${value}`);
            
            // Try dynamic patterns first (schema-driven)
            if (dynamicPatterns && dynamicPatterns.length > 0) {
                console.log(`🔍 Testing ${key} against ${dynamicPatterns.length} patterns:`);
                for (const pattern of dynamicPatterns) {
                    console.log(`  Testing pattern ${pattern.type}: ${pattern.regex.source}`);
                    const match = key.match(pattern.regex);
                    if (match) {
                        console.log(`✅ Matched dynamic pattern for ${key}:`, pattern);
                        console.log(`    Match groups:`, match);
                        
                        if (pattern.type === 'flattened_union') {
                            // Handle flattened union fields: bike_stock_0_bike_brand -> brand (flatten directly)
                            const unionProp = pattern.unionProperty;
                            cleanKey = unionProp;
                            cleanItem[cleanKey] = value;
                            console.log(`→ Flattened union field: ${key} -> ${cleanKey} = ${value}`);
                            
                            // Detect union type from form data if available
                            if (!unionTypeSelected && item.bike) {
                                unionTypeSelected = item.bike;
                                console.log(`🎯 Detected union type selection: ${unionTypeSelected}`);
                            }
                            
                            processed = true;
                            break;
                        } else if (pattern.type === 'flattened_direct') {
                            // Handle flattened direct fields: bike_stock_0_quantity -> quantity (flatten directly)
                            const directField = pattern.directField;
                            cleanKey = directField;
                            cleanItem[cleanKey] = value;
                            console.log(`→ Flattened direct field: ${key} -> ${cleanKey} = ${value}`);
                            processed = true;
                            break;
                        } else if (pattern.type === 'deep_nested_union') {
                            // Handle deep nested union fields: fan_stock_0_fan_brand -> fan.brand
                            const unionProp = pattern.unionProperty;
                            const unionField = pattern.unionField;
                            
                            if (!nestedObjects[unionField]) {
                                nestedObjects[unionField] = {};
                            }
                            nestedObjects[unionField][unionProp] = value;
                            console.log(`→ Created deep nested union field: ${unionField}.${unionProp} = ${value}`);
                            processed = true;
                            break;
                        } else if (pattern.type === 'nested_array_direct') {
                            // Handle direct fields in nested arrays: fan_stock_0_quantity -> quantity
                            cleanKey = pattern.directField;
                            cleanItem[cleanKey] = value;
                            console.log(`→ Cleaned nested array direct field: ${key} -> ${cleanKey} = ${value}`);
                            processed = true;
                            break;
                        } else if (pattern.type === 'nested_array_generic') {
                            // Handle generic nested array fields
                            cleanKey = match[1];
                            cleanItem[cleanKey] = value;
                            console.log(`→ Cleaned nested array generic field: ${key} -> ${cleanKey} = ${value}`);
                            processed = true;
                            break;
                        } else if (pattern.type === 'simple_nested') {
                            // Handle simple nested object fields
                            const fieldName = pattern.nestedProperty;
                            const nestedObjName = pattern.nestedObject;
                            
                            if (!nestedObjects[nestedObjName]) {
                                nestedObjects[nestedObjName] = {};
                            }
                            nestedObjects[nestedObjName][fieldName] = value;
                            console.log(`→ Created simple nested field: ${nestedObjName}.${fieldName} = ${value}`);
                            processed = true;
                            break;
                        } else if (pattern.type === 'reference_nested') {
                            // Handle reference nested fields: bike_sales_0_customer_review_rating -> customer_review.rating
                            const refField = pattern.referenceField;
                            const refProp = pattern.referenceProperty;
                            
                            if (!nestedObjects[refField]) {
                                nestedObjects[refField] = {};
                            }
                            nestedObjects[refField][refProp] = value;
                            console.log(`→ Created reference nested field: ${refField}.${refProp} = ${value}`);
                            processed = true;
                            break;
                        } else if (pattern.type === 'direct') {
                            // Handle direct fields
                            cleanKey = match[1];
                            cleanItem[cleanKey] = value;
                            console.log(`→ Cleaned direct field: ${key} -> ${cleanKey} = ${value}`);
                            processed = true;
                            break;
                        }
                    }
                }
            }
            
            // Fallback to legacy pattern matching if not processed by dynamic patterns
            if (!processed && arrayFieldPatterns && arrayFieldPatterns.length > 0) {
                console.log(`⚠️ Using fallback pattern matching for: ${key}`);
                
                // Create dynamic regex pattern from array field patterns
                const escapedPatterns = arrayFieldPatterns.map(pattern => 
                    pattern.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
                );
                const dynamicPrefixPattern = new RegExp(`^(?:${escapedPatterns.join('|')})_\\d+_(.+)$`);
                
                const prefixMatch = key.match(dynamicPrefixPattern);
                if (prefixMatch) {
                    cleanKey = prefixMatch[1];
                    cleanItem[cleanKey] = value;
                    console.log(`→ Legacy cleaned field name: ${key} -> ${cleanKey} = ${value}`);
                    processed = true;
                }
            }
            
            // Handle unprocessed fields
            if (!processed) {
                // Handle customer_review fields specially (legacy support)
                if (cleanKey.startsWith('customer_review_')) {
                    const reviewField = cleanKey.replace('customer_review_', '');
                    if (!nestedObjects.customer_review) {
                        nestedObjects.customer_review = {};
                    }
                    nestedObjects.customer_review[reviewField] = value;
                    console.log(`→ Created customer_review field: ${reviewField} = ${value}`);
                } else {
                    // Direct assignment for unprocessed fields
                    cleanItem[cleanKey] = value;
                    console.log(`→ Direct assignment: ${cleanKey} = ${value}`);
                }
            }
        });
        
        // Add union type discriminator if union fields were detected
        if (unionTypeSelected || (item.bike && typeof item.bike === 'string')) {
            const bikeType = unionTypeSelected || item.bike;
            // Convert discriminator values to readable form
            const bikeTypeMap = {
                'rootmodel_mountainbike': 'MountainBike',
                'rootmodel_roadbike': 'RoadBike', 
                'rootmodel_electricbike': 'ElectricBike'
            };
            cleanItem['bike'] = bikeTypeMap[bikeType] || bikeType;
            console.log(`🎯 Added union type discriminator: bike = ${cleanItem['bike']}`);
        }
        
        // Merge nested objects back into the clean item
        Object.keys(nestedObjects).forEach(objKey => {
            cleanItem[objKey] = nestedObjects[objKey];
            console.log(`→ Merged nested object: ${objKey}`, nestedObjects[objKey]);
        });
        
        console.log('Final cleaned item:', cleanItem);
        console.log('=== END cleanupFieldNames DEBUG ===');
        
        return cleanItem;
    }
}

/**
 * Form Data Utilities
 * Helper functions for form data processing
 */
class FormDataUtils {
    static parseFieldNameFromInputId(inputId) {
        if (inputId.startsWith('field-')) {
            return inputId.replace('field-', '');
        }
        if (inputId.startsWith('nested-')) {
            return inputId.replace('nested-', '').replace(/-/g, '.');
        }
        const parts = inputId.split('-');
        if (parts.length >= 3 && /^\d+$/.test(parts[1])) {
            return parts.slice(2).join('_');
        }
        return inputId;
    }

    static setNestedFieldValue(obj, fieldPath, value) {
        const keys = fieldPath.split('.');
        let current = obj;
        
        for (let i = 0; i < keys.length - 1; i++) {
            const key = keys[i];
            if (!current[key] || typeof current[key] !== 'object') {
                current[key] = {};
            }
            current = current[key];
        }
        
        current[keys[keys.length - 1]] = value;
    }

    static sanitizeFieldName(labelText) {
        return labelText.toLowerCase()
            .replace(/[^\w\s]/g, '')
            .replace(/\s+/g, '_')
            .trim();
    }

    static extractArrayFieldName(container) {
        return container.getAttribute('data-field-name') || 
               container.getAttribute('data-array-field') ||
               container.id?.replace(/^array-/, '') ||
               this.sanitizeFieldName(container.closest('.form-group')?.querySelector('.form-label')?.textContent || 'items');
    }

    static collectArrayData(arrayContainer) {
        const arrayData = [];
        const items = arrayContainer.querySelectorAll('.array-item, [class*="item"]');
        
        items.forEach((item, index) => {
            const itemData = {};
            const itemInputs = item.querySelectorAll('input, select, textarea');
            
            itemInputs.forEach(input => {
                if (input.id && input.value.trim()) {
                    const propName = this.parseFieldNameFromInputId(input.id);
                    let value = input.value.trim();
                    
                    if (input.type === 'number' && value !== '') {
                        value = parseFloat(value) || 0;
                    }
                    
                    itemData[propName] = value;
                }
            });
            
            if (Object.keys(itemData).length > 0) {
                arrayData.push(itemData);
            }
        });
        
        return arrayData;
    }
}

// Export for global access
window.JSONResponseBuilder = JSONResponseBuilder;
window.FormDataUtils = FormDataUtils;