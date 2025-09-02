/**
 * Array Manager
 * Specialized manager for handling array operations in dynamic forms
 * Handles complex array item generation, nested objects, and union fields
 */

class ArrayManager {
    constructor(dataManager, schemaCache, fieldCache) {
        this.dataManager = dataManager;
        this.schemaCache = schemaCache;
        this.fieldCache = fieldCache;
        this.API_BASE_URL = 'http://localhost:8000/api/v1/custom-workflows';
    }

    /**
     * Add array item by field name (main entry point)
     */
    async addArrayItemByName(currentSchema, fieldName) {
        const fieldKey = `${currentSchema}_${fieldName}`;
        const field = this.fieldCache[fieldKey];
        if (!field) {
            console.error(`Field definition not found in cache for: ${fieldKey}`);
            alert('Field definition not found. Please try refreshing the page.');
            return;
        }
        return await this.addArrayItem(currentSchema, fieldName, field);
    }

    /**
     * Add array item with full schema resolution
     */
    async addArrayItem(currentSchema, fieldName, field) {
        try {
            const schema = await this.fetchSchema(currentSchema);
            const arrayContainer = document.getElementById(`array-${fieldName}`);
            if (!arrayContainer) return;

            // Initialize data structure
            const itemIndex = this.dataManager.addArrayItem(currentSchema, fieldName, {});
            
            const ref = field.items?.$ref;
            if (!ref) {
                console.error('Array item schema reference ($ref) not found.');
                return;
            }

            const schemaName = ref.split('/').pop();
            const itemSchema = schema.schemas[schemaName] || schema.schemas.RootModel?.definitions?.[schemaName];
            if (!itemSchema) {
                console.error(`Could not find schema for array item: ${ref}`);
                return;
            }
            
            const itemHtml = this.generateArrayItemHtml(currentSchema, fieldName, itemIndex, itemSchema, schema.schemas);
            arrayContainer.insertAdjacentHTML('beforeend', itemHtml);
            
            const itemData = { ...(itemSchema.default_values || {}) };
            this.dataManager.updateArrayItemData(currentSchema, fieldName, itemIndex, '', itemData);
            console.log(`ArrayManager: Added array item for ${fieldName}:`, itemData);
        } catch (error) {
            console.error('Failed to add array item:', error);
        }
    }

    /**
     * Generate HTML for array item
     */
    generateArrayItemHtml(currentSchema, fieldName, itemIndex, itemSchema, allSchemas) {
        const itemId = `${fieldName}-item-${itemIndex}`;
        let displayName = BaseManager.cleanDisplayName(itemSchema.title || itemSchema.model_name) || `Item ${itemIndex + 1}`;
        
        let fieldsHtml = '';
        if (itemSchema.properties) {
            const displayOrder = itemSchema.ui_metadata?.display_order || Object.keys(itemSchema.properties);
            for (const propName of displayOrder) {
                const prop = itemSchema.properties[propName];
                if (prop) {
                    fieldsHtml += this.generateArrayItemFieldHtml(currentSchema, fieldName, itemIndex, propName, prop, allSchemas);
                }
            }
        }
        
        console.log(`🔧 ArrayManager: Generating array item ${itemIndex} for field: ${fieldName} (${displayName})`);
        
        return `
            <div class="enhanced-card" id="${itemId}" style="margin-left: 1rem; border-left: 3px solid var(--primary-blue); padding: 16px;">
                <div class="d-flex align-items-center justify-content-between mb-2">
                    <h6 class="mb-0 text-muted" style="margin-left: 8px;">${displayName} #${itemIndex + 1}</h6>
                    <div class="d-flex align-items-center gap-2">
                        <button class="btn btn-link text-secondary p-2 d-flex align-items-center justify-content-center" onclick="window.arrayManager.toggleArrayItem('${itemId}')" title="Toggle visibility" style="border: none; width: 32px; height: 32px; border-radius: 50%; background-color: rgba(108, 117, 125, 0.1);">
                            <i class="bi bi-eye" id="${itemId}-toggle-icon" style="font-size: 14px;"></i>
                        </button>
                        <button class="btn btn-link text-danger p-2 d-flex align-items-center justify-content-center" onclick="window.arrayManager.removeArrayItem('${itemId}', '${fieldName}')" title="Remove item" style="border: none; width: 32px; height: 32px; border-radius: 50%; background-color: rgba(220, 53, 69, 0.1);">
                            <i class="bi bi-trash" style="font-size: 14px;"></i>
                        </button>
                    </div>
                </div>
                <div class="array-item-content" id="${itemId}-content">
                    ${fieldsHtml}
                </div>
            </div>
        `;
    }

    /**
     * Generate HTML for individual array item field
     */
    generateArrayItemFieldHtml(currentSchema, fieldName, itemIndex, propName, prop, allSchemas) {
        const rawDisplayName = prop.display_name || prop.title || propName;
        const displayName = BaseManager.cleanDisplayName(rawDisplayName);
        const fieldId = `${fieldName}-${itemIndex}-${propName}`;
        
        // Always prioritize $ref object references over other field types
        if (prop.$ref) {
            return this.generateArrayItemNestedObjectField(currentSchema, fieldName, itemIndex, propName, prop, allSchemas);
        }
        
        if (prop.anyOf || prop.union_options || prop.ui_component === 'union_select') {
            return this.generateArrayItemUnionField(currentSchema, fieldName, itemIndex, propName, prop, allSchemas);
        }
        if (prop.type === 'array' || prop.ui_component === 'array') {
            return this.generateNestedArrayField(currentSchema, fieldName, itemIndex, propName, prop, allSchemas);
        }

        const onChange = `onchange="window.arrayManager.updateArrayItemData('${currentSchema}', '${fieldName}', ${itemIndex}, '${propName}', this.value)"`;
        const onChangeFloat = `onchange="window.arrayManager.updateArrayItemData('${currentSchema}', '${fieldName}', ${itemIndex}, '${propName}', parseFloat(this.value))"`;

        switch (prop.type) {
            case 'number':
            case 'integer':
                 return `
                    <div class="mb-3">
                        <label class="form-label" for="${fieldId}">${displayName}</label>
                        <input type="number" class="form-control" id="${fieldId}" 
                               placeholder="Enter ${displayName.toLowerCase()}" 
                               ${onChangeFloat}>
                    </div>`;
            default:
                return `
                    <div class="mb-3">
                        <label class="form-label" for="${fieldId}">${displayName}</label>
                        <input type="text" class="form-control" id="${fieldId}" 
                               placeholder="Enter ${displayName.toLowerCase()}" 
                               ${onChange}>
                    </div>`;
        }
    }

    /**
     * Initialize array item union form data (delegates to DataManager)
     */
    initializeArrayItemUnionFormData(currentSchema, fieldName, itemIndex, propName, schema) {
        this.dataManager.initializeArrayItemUnionFormData(currentSchema, fieldName, itemIndex, propName, schema);
    }

    /**
     * Auto-add first array items for schema
     */
    async autoAddFirstArrayItems(currentSchema, rootModel) {
        if (!rootModel.properties) return;
        for (const [fieldName, field] of Object.entries(rootModel.properties)) {
            if (field.type === 'array' && field.ui_component === 'array') {
                setTimeout(async () => {
                    await this.addArrayItemByName(currentSchema, fieldName);
                }, 100);
            }
        }
    }

    /**
     * Find main array field in model (for entity management)
     */
    findMainArrayField(model) {
        if (!model.properties) return null;
        for (const [fieldName, field] of Object.entries(model.properties)) {
            if (field.type === 'array' && field.ui_component === 'array') {
                return { name: fieldName, field: field };
            }
        }
        return null;
    }

    /**
     * Add entity (main entry point for adding new entities)
     */
    async addEntity(currentSchema) {
        if (!currentSchema) {
            alert('Please select a schema first');
            return;
        }
        try {
            const schema = await this.fetchSchema(currentSchema);
            const rootModel = schema.schemas.RootModel;
            const arrayField = this.findMainArrayField(rootModel);
            if (arrayField) {
                this.addArrayItem(currentSchema, arrayField.name, arrayField.field);
            } else {
                alert('No main entity array found in schema');
            }
        } catch (error) {
            console.error('Failed to add entity:', error);
        }
    }

    /**
     * Generate array field HTML (for initial form generation)
     */
    generateArrayField(currentSchema, fieldName, field) {
        const rawDisplayName = field.display_name || field.title || fieldName;
        const displayName = BaseManager.cleanDisplayName(rawDisplayName);
        
        // CRITICAL: Cache the field definition for later use in addArrayItemByName
        this.fieldCache[`${currentSchema}_${fieldName}`] = field;
        console.log(`🔧 ArrayManager: Generating array field container for: ${fieldName} (${displayName})`);
        
        return `
            <div class="card mb-4">
                <div class="card-body">
                    <div class="d-flex align-items-center justify-content-between mb-3">
                        <h5 class="card-title mb-0">${displayName}</h5>
                        <button class="btn-plus" onclick="window.arrayManager.addArrayItemByName('${currentSchema}', '${fieldName}')" title="Add ${displayName}">+</button>
                    </div>
                    <div id="array-${fieldName}"></div>
                </div>
            </div>
        `;
    }

    /**
     * Validate array data
     */
    validateArrayData(currentSchema, fieldName, data) {
        const errors = [];
        if (!Array.isArray(data)) {
            errors.push(`${fieldName} must be an array`);
            return { isValid: false, errors };
        }

        // Validate each array item
        data.forEach((item, index) => {
            if (typeof item === 'object' && item !== null) {
                // Could add more specific validation based on schema
                const itemKeys = Object.keys(item);
                if (itemKeys.length === 0) {
                    errors.push(`${fieldName}[${index}] is empty`);
                }
            }
        });

        return { isValid: errors.length === 0, errors };
    }

    /**
     * Get array statistics
     */
    getArrayStats(currentSchema, fieldName) {
        const data = this.dataManager.getFormDataForSchema(currentSchema);
        const arrayData = data[fieldName];
        
        if (!Array.isArray(arrayData)) {
            return { totalItems: 0, filledItems: 0, emptyItems: 0 };
        }

        const stats = {
            totalItems: arrayData.length,
            filledItems: 0,
            emptyItems: 0,
            averageFieldsPerItem: 0
        };

        let totalFields = 0;
        arrayData.forEach(item => {
            const itemKeys = Object.keys(item || {});
            if (itemKeys.length > 0) {
                stats.filledItems++;
                totalFields += itemKeys.length;
            } else {
                stats.emptyItems++;
            }
        });

        stats.averageFieldsPerItem = stats.filledItems > 0 ? totalFields / stats.filledItems : 0;
        return stats;
    }

    /**
     * Generate nested object field within array item
     */
    generateArrayItemNestedObjectField(currentSchema, fieldName, itemIndex, propName, prop, allSchemas) {
        const displayName = prop.display_name || prop.title || propName;
        
        // Resolve the $ref to get the referenced schema
        const schemaRef = prop.$ref;
        if (!schemaRef) {
            console.error(`No $ref found for array item nested object field: ${propName}`);
            return this.generateArrayItemFallbackField(currentSchema, fieldName, itemIndex, propName, prop);
        }
        
        const schemaName = schemaRef.split('/').pop();
        const referencedSchema = allSchemas[schemaName] || 
                               allSchemas.RootModel?.definitions?.[schemaName] ||
                               this.schemaCache[currentSchema]?.schemas?.RootModel?.definitions?.[schemaName];
        
        if (!referencedSchema) {
            console.error(`Referenced schema not found for array item: ${schemaName}`);
            return this.generateArrayItemFallbackField(currentSchema, fieldName, itemIndex, propName, prop);
        }
        
        // Generate nested fields HTML for the array item context
        let nestedFieldsHtml = '';
        if (referencedSchema.properties) {
            const displayOrder = referencedSchema.ui_metadata?.display_order || Object.keys(referencedSchema.properties);
            for (const nestedPropName of displayOrder) {
                const nestedProp = referencedSchema.properties[nestedPropName];
                if (nestedProp) {
                    nestedFieldsHtml += this.generateArrayItemNestedObjectFieldHtml(currentSchema, fieldName, itemIndex, propName, nestedPropName, nestedProp);
                }
            }
        }
        
        return `
            <div class="form-group" style="margin-top: 1rem; padding: 1rem; border: 1px solid var(--bs-border-color); border-radius: 6px; background-color: #f8f9fa;">
                <div class="form-label" style="font-weight: 600; margin-bottom: 0.75rem; color: var(--bs-dark);">${displayName}</div>
                <div class="nested-object-fields">
                    ${nestedFieldsHtml}
                </div>
            </div>
        `;
    }

    /**
     * Generate HTML for nested object field within array item
     */
    generateArrayItemNestedObjectFieldHtml(currentSchema, fieldName, itemIndex, parentPropName, nestedPropName, nestedProp) {
        const displayName = nestedProp.display_name || nestedProp.title || nestedPropName;
        const fieldId = `${fieldName}-${itemIndex}-${parentPropName}-${nestedPropName}`;
        const onChange = `onchange="window.arrayManager.updateArrayItemNestedObjectFieldData('${currentSchema}', '${fieldName}', ${itemIndex}, '${parentPropName}', '${nestedPropName}', this.value)"`;
        const onChangeFloat = `onchange="window.arrayManager.updateArrayItemNestedObjectFieldData('${currentSchema}', '${fieldName}', ${itemIndex}, '${parentPropName}', '${nestedPropName}', parseFloat(this.value))"`;

        switch (nestedProp.type) {
            case 'number':
                const numConf = nestedProp.number_config || {};
                return `
                    <div class="mb-3">
                        <label class="form-label" for="${fieldId}">${displayName}</label>
                        <input type="number" class="form-control" id="${fieldId}"
                               min="${numConf.min || ''}" max="${numConf.max || ''}" step="${numConf.step || 0.01}"
                               placeholder="Enter ${displayName.toLowerCase()}" ${onChangeFloat}>
                        ${nestedProp.description ? `<div class="form-text">${nestedProp.description}</div>` : ''}
                    </div>
                `;
            case 'integer':
                return `
                    <div class="mb-3">
                        <label class="form-label" for="${fieldId}">${displayName}</label>
                        <input type="number" class="form-control" id="${fieldId}"
                               step="1" placeholder="Enter ${displayName.toLowerCase()}" ${onChangeFloat}>
                        ${nestedProp.description ? `<div class="form-text">${nestedProp.description}</div>` : ''}
                    </div>
                `;
            default:
                return `
                    <div class="mb-3">
                        <label class="form-label" for="${fieldId}">${displayName}</label>
                        <input type="text" class="form-control" id="${fieldId}"
                               placeholder="Enter ${displayName.toLowerCase()}" ${onChange}>
                        ${nestedProp.description ? `<div class="form-text">${nestedProp.description}</div>` : ''}
                    </div>
                `;
        }
    }

    /**
     * Generate fallback field for array items
     */
    generateArrayItemFallbackField(currentSchema, fieldName, itemIndex, propName, prop) {
        const displayName = prop.display_name || prop.title || propName;
        const fieldId = `${fieldName}-${itemIndex}-${propName}`;
        return `
            <div class="form-group">
                <label class="form-label">${displayName}</label>
                <input type="text" class="form-input" id="${fieldId}"
                       placeholder="Enter ${displayName.toLowerCase()}"
                       onchange="window.arrayManager.updateArrayItemData('${currentSchema}', '${fieldName}', ${itemIndex}, '${propName}', this.value)">
                <div class="form-text text-warning">Unable to resolve nested object schema</div>
            </div>
        `;
    }

    /**
     * Generate nested array field
     */
    generateNestedArrayField(currentSchema, parentFieldName, parentIndex, fieldName, field, allSchemas) {
        const displayName = field.display_name || field.title || fieldName;
        const nestedFieldId = `${parentFieldName}-${parentIndex}-${fieldName}`;
        this.fieldCache[`${currentSchema}_${nestedFieldId}`] = field;
        return `
            <div style="margin-top: 1.5rem; padding-top: 1rem; border-top: 1px solid var(--border-color);">
                <div class="section-header-with-plus">
                    <span>${displayName}</span>
                    <button class="btn-plus" onclick="window.arrayManager.addNestedArrayItem('${currentSchema}', '${nestedFieldId}')" title="Add ${displayName}">+</button>
                </div>
                <div id="array-${nestedFieldId}" class="array-container"></div>
            </div>
        `;
    }

    /**
     * Add nested array item
     */
    async addNestedArrayItem(currentSchema, nestedFieldId) {
        const fieldKey = `${currentSchema}_${nestedFieldId}`;
        const field = this.fieldCache[fieldKey];
        if (!field) {
            console.error(`Nested field definition not found in cache for: ${fieldKey}`);
            return;
        }
        return await this.addArrayItem(currentSchema, nestedFieldId, field);
    }

    /**
     * Generate union field for array items
     */
    generateArrayItemUnionField(currentSchema, fieldName, itemIndex, propName, prop, allSchemas) {
        const rawDisplayName = prop.display_name || prop.title || propName;
        const displayName = BaseManager.cleanDisplayName(rawDisplayName);
        let unionOptions = prop.union_options || [];
        
        if (unionOptions.length === 0 && prop.anyOf) {
            unionOptions = prop.anyOf.map(option => {
                if (!option.$ref) return null;
                const schemaName = option.$ref.split('/').pop();
                return {
                    value: schemaName.toLowerCase(),
                    label: BaseManager.cleanDisplayName(schemaName),
                    schema_ref: option.$ref,
                };
            }).filter(Boolean);
        }
        
        // Cache the union options for array item rendering
        const cacheKey = `${currentSchema}_${fieldName}_${itemIndex}_${propName}_union`;
        this.fieldCache[cacheKey] = {
            unionOptions: unionOptions,
            allSchemas: allSchemas
        };
        
        let optionsHtml = unionOptions.map(option => `
            <div class="option-card" onclick="window.arrayManager.selectArrayItemUnionOption('${currentSchema}', '${fieldName}', ${itemIndex}, '${propName}', '${option.value}', this)">
                <span class="option-name">${BaseManager.cleanDisplayName(option.label)}</span>
            </div>
        `).join('');

        const unionFieldsId = `union-fields-${fieldName}-${itemIndex}-${propName}`;
        return `
            <div class="form-group">
                <label class="form-label">${displayName}</label>
                <div class="option-selection">${optionsHtml}</div>
                <div id="${unionFieldsId}" class="union-fields-container mt-3"></div>
            </div>
        `;
    }

    /**
     * Select union option for array item
     */
    async selectArrayItemUnionOption(currentSchema, fieldName, itemIndex, propName, value, element) {
        element.parentNode.querySelectorAll('.option-card').forEach(card => card.classList.remove('selected'));
        element.classList.add('selected');
        this.dataManager.updateArrayItemData(currentSchema, fieldName, itemIndex, propName, value);
        
        // Render dynamic fields for the selected union option in array item
        await this.renderArrayItemUnionFields(currentSchema, fieldName, itemIndex, propName, value);
    }

    /**
     * Render union fields for array item
     */
    async renderArrayItemUnionFields(currentSchema, fieldName, itemIndex, propName, selectedValue) {
        try {
            const cacheKey = `${currentSchema}_${fieldName}_${itemIndex}_${propName}_union`;
            const cachedData = this.fieldCache[cacheKey];
            if (!cachedData) {
                console.error(`Array union field data not found for: ${cacheKey}`);
                return;
            }

            const { unionOptions, allSchemas } = cachedData;
            const selectedOption = unionOptions.find(option => option.value === selectedValue);
            if (!selectedOption) {
                console.error(`Selected array union option not found: ${selectedValue}`);
                return;
            }

            // Get the schema for the selected union type
            const schemaRef = selectedOption.schema_ref;
            if (!schemaRef) {
                console.error(`Schema reference not found for array union option: ${selectedValue}`);
                return;
            }

            const schemaName = schemaRef.split('/').pop();
            const selectedSchema = allSchemas[schemaName] || 
                                allSchemas.RootModel?.definitions?.[schemaName] ||
                                this.schemaCache[currentSchema]?.schemas?.RootModel?.definitions?.[schemaName];

            if (!selectedSchema) {
                console.error(`Schema not found for array union: ${schemaName}`);
                return;
            }

            // Clear previous union fields
            const unionFieldsId = `union-fields-${fieldName}-${itemIndex}-${propName}`;
            const container = document.getElementById(unionFieldsId);
            if (container) {
                container.innerHTML = '';
            }

            // Generate fields HTML for the selected schema
            const fieldsHtml = this.generateArrayItemUnionSchemaFields(currentSchema, fieldName, itemIndex, propName, selectedSchema);
            if (container) {
                container.innerHTML = fieldsHtml;
            }

            // Initialize form data for the selected union type
            this.dataManager.initializeArrayItemUnionFormData(currentSchema, fieldName, itemIndex, propName, selectedSchema);

        } catch (error) {
            console.error('Failed to render array item union fields:', error);
        }
    }

    /**
     * Generate HTML for array item union schema fields
     */
    generateArrayItemUnionSchemaFields(currentSchema, fieldName, itemIndex, propName, schema) {
        if (!schema.properties) return '';
        
        let fieldsHtml = '<div class="union-schema-fields mt-3 p-3" style="border: 1px solid var(--bs-border-color); border-radius: 6px; background-color: #f8f9fa;">';
        
        const displayOrder = schema.ui_metadata?.display_order || Object.keys(schema.properties);
        for (const schemaPropName of displayOrder) {
            const schemaProp = schema.properties[schemaPropName];
            if (schemaProp) {
                fieldsHtml += this.generateArrayItemUnionFieldHtml(currentSchema, fieldName, itemIndex, propName, schemaPropName, schemaProp);
            }
        }
        
        fieldsHtml += '</div>';
        return fieldsHtml;
    }

    /**
     * Generate HTML for individual array item union field
     */
    generateArrayItemUnionFieldHtml(currentSchema, fieldName, itemIndex, propName, schemaPropName, schemaProp) {
        const displayName = schemaProp.display_name || schemaProp.title || schemaPropName;
        const fieldId = `${fieldName}-${itemIndex}-${propName}-${schemaPropName}`;
        const onChange = `onchange="window.arrayManager.updateArrayItemUnionFieldData('${currentSchema}', '${fieldName}', ${itemIndex}, '${propName}', '${schemaPropName}', this.value)"`;
        const onChangeFloat = `onchange="window.arrayManager.updateArrayItemUnionFieldData('${currentSchema}', '${fieldName}', ${itemIndex}, '${propName}', '${schemaPropName}', parseFloat(this.value))"`;

        switch (schemaProp.type) {
            case 'number':
                const numConf = schemaProp.number_config || {};
                return `
                    <div class="mb-3">
                        <label class="form-label" for="${fieldId}">${displayName}</label>
                        <input type="number" class="form-control" id="${fieldId}"
                               min="${numConf.min || ''}" max="${numConf.max || ''}" step="${numConf.step || 0.01}"
                               placeholder="Enter ${displayName.toLowerCase()}" ${onChangeFloat}>
                        ${schemaProp.description ? `<div class="form-text">${schemaProp.description}</div>` : ''}
                    </div>
                `;
            case 'integer':
                return `
                    <div class="mb-3">
                        <label class="form-label" for="${fieldId}">${displayName}</label>
                        <input type="number" class="form-control" id="${fieldId}"
                               step="1" placeholder="Enter ${displayName.toLowerCase()}" ${onChangeFloat}>
                        ${schemaProp.description ? `<div class="form-text">${schemaProp.description}</div>` : ''}
                    </div>
                `;
            default:
                return `
                    <div class="mb-3">
                        <label class="form-label" for="${fieldId}">${displayName}</label>
                        <input type="text" class="form-control" id="${fieldId}"
                               placeholder="Enter ${displayName.toLowerCase()}" ${onChange}>
                        ${schemaProp.description ? `<div class="form-text">${schemaProp.description}</div>` : ''}
                    </div>
                `;
        }
    }

    /**
     * Update array item data (delegates to DataManager)
     */
    updateArrayItemData(currentSchema, fieldName, itemIndex, propName, value) {
        this.dataManager.updateArrayItemData(currentSchema, fieldName, itemIndex, propName, value);
    }

    /**
     * Update array item nested object field data (delegates to DataManager)
     */
    updateArrayItemNestedObjectFieldData(currentSchema, fieldName, itemIndex, parentPropName, nestedPropName, value) {
        this.dataManager.updateArrayItemNestedObjectFieldData(currentSchema, fieldName, itemIndex, parentPropName, nestedPropName, value);
    }

    /**
     * Update array item union field data (delegates to DataManager)
     */
    updateArrayItemUnionFieldData(currentSchema, fieldName, itemIndex, propName, schemaPropName, value) {
        this.dataManager.updateArrayItemUnionFieldData(currentSchema, fieldName, itemIndex, propName, schemaPropName, value);
    }

    /**
     * Remove array item
     */
    removeArrayItem(currentSchema, fieldName, itemIndex) {
        const itemId = `${fieldName}-item-${itemIndex}`;
        document.getElementById(itemId)?.remove();
        this.dataManager.removeArrayItem(currentSchema, fieldName, itemIndex);
        console.log(`ArrayManager: Removed array item ${itemIndex} from ${fieldName}`);
    }

    /**
     * Fetch schema (delegates to main workflow)
     */
    async fetchSchema(workflowName) {
        if (this.schemaCache[workflowName]) {
            return this.schemaCache[workflowName];
        }
        try {
            const apiCfg = window.API_CONFIG || {};
            const schemaEndpointTmpl = apiCfg.endpoints?.workflowSchemaRetriever;
            const baseUrl = apiCfg.baseUrl;
            // Fallback to legacy API_BASE_URL if config missing
            const url = (baseUrl && schemaEndpointTmpl)
                ? `${baseUrl}${schemaEndpointTmpl.replace('{custom-workflow-name}', encodeURIComponent(workflowName))}${schemaEndpointTmpl.endsWith('/') ? '' : '/'}`
                : `${this.API_BASE_URL}/schema/${encodeURIComponent(workflowName)}/`;
            const response = await fetch(url);
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            const schema = await response.json();
            this.schemaCache[workflowName] = schema;
            return schema;
        } catch (error) {
            console.error(`Failed to fetch schema for ${workflowName}:`, error);
            throw new Error(`Schema fetch failed: ${workflowName}`);
        }
    }

    /**
     * Toggle array item visibility
     */
    toggleArrayItem(itemId) {
        const content = document.getElementById(`${itemId}-content`);
        const toggleButton = document.querySelector(`#${itemId} .array-toggle-btn`);
        
        if (!content || !toggleButton) {
            console.error(`Toggle elements not found for item: ${itemId}`);
            return;
        }

        const isCollapsed = content.classList.contains('collapsed');
        
        if (isCollapsed) {
            // Expand
            content.classList.remove('collapsed');
            toggleButton.classList.remove('collapsed');
            toggleButton.innerHTML = '<i class="bi bi-chevron-down"></i>';
            toggleButton.setAttribute('aria-expanded', 'true');
        } else {
            // Collapse
            content.classList.add('collapsed');
            toggleButton.classList.add('collapsed');
            toggleButton.innerHTML = '<i class="bi bi-chevron-right"></i>';
            toggleButton.setAttribute('aria-expanded', 'false');
        }
        
        console.log(`ArrayManager: Toggled ${itemId} - ${isCollapsed ? 'expanded' : 'collapsed'}`);
    }

    /**
     * Toggle nested object field visibility
     */
    toggleNestedObjectField(fieldId) {
        const content = document.getElementById(`${fieldId}-content`);
        const toggleButton = document.querySelector(`#${fieldId}-header .toggle-button`);
        
        if (!content || !toggleButton) {
            console.error(`Toggle elements not found for nested object: ${fieldId}`);
            return;
        }

        const isCollapsed = content.classList.contains('collapsed');
        
        if (isCollapsed) {
            content.classList.remove('collapsed');
            toggleButton.classList.remove('collapsed');
            toggleButton.innerHTML = '▼';
        } else {
            content.classList.add('collapsed');
            toggleButton.classList.add('collapsed');
            toggleButton.innerHTML = '▶';
        }
    }

    /**
     * Toggle union fields visibility
     */
    toggleUnionFields(fieldId) {
        const content = document.getElementById(`${fieldId}-fields`);
        const toggleButton = document.querySelector(`#${fieldId}-header .toggle-button`);
        
        if (!content || !toggleButton) {
            console.error(`Toggle elements not found for union field: ${fieldId}`);
            return;
        }

        const isCollapsed = content.classList.contains('collapsed');
        
        if (isCollapsed) {
            content.classList.remove('collapsed');
            toggleButton.classList.remove('collapsed');
            toggleButton.innerHTML = '▼';
        } else {
            content.classList.add('collapsed');
            toggleButton.classList.add('collapsed');
            toggleButton.innerHTML = '▶';
        }
    }

    /**
     * Bulk toggle all array items
     */
    bulkToggleArrayItems(action = 'toggle') {
        const arrayItems = document.querySelectorAll('[id$="-item-0"], [id$="-item-1"], [id$="-item-2"], [id$="-item-3"], [id$="-item-4"], [id$="-item-5"], [id$="-item-6"], [id$="-item-7"], [id$="-item-8"], [id$="-item-9"]');
        
        arrayItems.forEach(item => {
            const itemId = item.id;
            const content = document.getElementById(`${itemId}-content`);
            const toggleButton = item.querySelector('.toggle-button');
            
            if (!content || !toggleButton) return;
            
            const isCurrentlyCollapsed = content.classList.contains('collapsed');
            
            switch (action) {
                case 'expand':
                    if (isCurrentlyCollapsed) {
                        this.toggleArrayItem(itemId);
                    }
                    break;
                case 'collapse':
                    if (!isCurrentlyCollapsed) {
                        this.toggleArrayItem(itemId);
                    }
                    break;
                case 'toggle':
                default:
                    this.toggleArrayItem(itemId);
                    break;
            }
        });
        
        console.log(`ArrayManager: Bulk ${action} performed on all array items`);
    }

    /**
     * Get toggle state for persistence
     */
    getToggleStates() {
        const states = {};
        const toggleableItems = document.querySelectorAll('.array-item-content, .nested-object-fields, .union-schema-fields');
        
        toggleableItems.forEach(item => {
            const itemId = item.id;
            if (itemId) {
                states[itemId] = !item.classList.contains('collapsed');
            }
        });
        
        return states;
    }

    /**
     * Restore toggle states from persistence
     */
    restoreToggleStates(states) {
        if (!states || typeof states !== 'object') return;
        
        Object.entries(states).forEach(([itemId, isExpanded]) => {
            const content = document.getElementById(itemId);
            const toggleButton = document.querySelector(`[onclick*="${itemId.replace('-content', '')}"] .toggle-button`);
            
            if (!content || !toggleButton) return;
            
            const isCurrentlyCollapsed = content.classList.contains('collapsed');
            
            // Only toggle if the current state doesn't match the desired state
            if (isExpanded && isCurrentlyCollapsed) {
                content.classList.remove('collapsed');
                toggleButton.classList.remove('collapsed');
                toggleButton.innerHTML = '▼';
            } else if (!isExpanded && !isCurrentlyCollapsed) {
                content.classList.add('collapsed');
                toggleButton.classList.add('collapsed');
                toggleButton.innerHTML = '▶';
            }
        });
        
        console.log('ArrayManager: Toggle states restored');
    }

    /**
     * Toggle visibility of array item content
     */
    toggleArrayItem(itemId) {
        const content = document.getElementById(`${itemId}-content`);
        const toggleIcon = document.getElementById(`${itemId}-toggle-icon`);
        
        if (!content || !toggleIcon) return;
        
        if (content.style.display === 'none') {
            content.style.display = 'block';
            toggleIcon.className = 'bi bi-eye';
        } else {
            content.style.display = 'none';
            toggleIcon.className = 'bi bi-eye-slash';
        }
    }

    /**
     * Remove array item from DOM and data
     */
    removeArrayItem(itemId, fieldName) {
        // Confirm deletion
        if (!confirm('Are you sure you want to remove this item?')) {
            return;
        }
        
        const itemElement = document.getElementById(itemId);
        if (!itemElement) return;
        
        // Extract item index from itemId (format: fieldName-index)
        const indexMatch = itemId.match(/-(\d+)$/);
        if (!indexMatch) return;
        
        const itemIndex = parseInt(indexMatch[1]);
        
        // Get current schema from the global workflow manager
        const currentSchema = window.dynamicWorkflow?.currentSchema;
        if (!currentSchema) {
            console.error('Cannot remove array item: no current schema found');
            return;
        }
        
        // Remove from DOM
        itemElement.remove();
        
        // Remove from data
        if (this.dataManager && typeof this.dataManager.removeArrayItem === 'function') {
            this.dataManager.removeArrayItem(currentSchema, fieldName, itemIndex);
        }
        
        console.log(`ArrayManager: Removed array item ${itemId} from field ${fieldName}`);
    }
}

// Create global instance for easy access from generated HTML
window.arrayManager = null; // Will be initialized by DynamicWorkflowManager

// Export for use in other modules
window.ArrayManager = ArrayManager;