/**
 * Dynamic Workflow Manager
 * Main coordinator for dynamic workflow functionality
 * Handles schema selection, form generation, and workflow processing
 */

class DynamicWorkflowManager {
    constructor() {
        // Dependencies
        this.dataManager = null;
        this.arrayManager = null;
        
        // State management
        this.currentSchema = null;
        this.availableWorkflows = [];
        this.schemaCache = {};
        this.fieldCache = {};
        this.schemasLoaded = false;
        
        // UI State
        this.showFormHeader = false;
        this.showFormActions = false;
        this.showResults = false;
        this.formTitle = 'Dynamic Form';
        this.dynamicFormHtml = '';
        this.resultsHtml = '';
        
        // Configuration
        this._isLoadingWorkflows = false;
    }

    /**
     * Initialize the workflow manager and dependencies
     */
    async init() {
        console.log('Dynamic Workflows System loaded');
        
        // Initialize dependencies
        this.initializeDependencies();
        
    // Load selected workflow
    await this.fetchWorkflow();
    }

    /**
     * Initialize dependency classes
     */
    initializeDependencies() {
        // Create data manager instance
        if (window.DataManager) {
            this.dataManager = new DataManager();
        }
        
        // Create array manager instance
        if (window.ArrayManager) {
            this.arrayManager = new ArrayManager(this.dataManager, this.schemaCache, this.fieldCache);
            // CRITICAL: Set global reference for HTML onclick handlers
            window.arrayManager = this.arrayManager;
        }
    }

    /**
     * Fetch workflows from API
     */
    async fetchWorkflow() {
        // Prevent multiple simultaneous calls
        if (this._isLoadingWorkflows) {
            console.log('[fetchWorkflow] Already loading workflow, skipping...');
            return;
        }

        this._isLoadingWorkflows = true;

        try {
            // Reset state first
            this.availableWorkflows = [];
            this.schemasLoaded = false;

            // Get workflow from URL
            const urlParams = new URLSearchParams(window.location.search);
            // Only accept `id` as the selector
            const selectedWorkflow = urlParams.get('id');
            if (!selectedWorkflow) {
                console.warn('[fetchWorkflow] No workflow selected in URL.');
                this.schemasLoaded = true;
                return;
            }
            console.log(`[fetchWorkflow] Processing selected workflow: ${selectedWorkflow}`);
            try {
                const schema = await this.fetchSchema(selectedWorkflow);
                const rootModel = schema.schemas.RootModel;
                const schemaTitle = this.getSchemaTitle(rootModel, selectedWorkflow);

                const workflow = {
                    name: selectedWorkflow,
                    title: schemaTitle,
                    description: rootModel.description || `Dynamic ${selectedWorkflow.replace(/_/g, ' ')} workflow`
                };

                this.availableWorkflows.push(workflow);
                console.log(`[fetchWorkflow] Successfully added workflow: ${selectedWorkflow}`, workflow);
            } catch (error) {
                console.error(`Failed to load schema for ${selectedWorkflow}:`, error);

                // Create unique fallback title
                const fallbackTitle = this.createFallbackTitle(selectedWorkflow);
                const fallbackWorkflow = {
                    name: selectedWorkflow,
                    title: fallbackTitle,
                    description: `${fallbackTitle} workflow (schema unavailable)`
                };

                this.availableWorkflows.push(fallbackWorkflow);
                console.log(`[fetchWorkflow] Added fallback workflow: ${selectedWorkflow}`, fallbackWorkflow);
            }

            this.schemasLoaded = true;
            console.log('[fetchWorkflow] Final availableWorkflows:', this.availableWorkflows);

        } catch (error) {
            console.error('[fetchWorkflow] Failed to fetch workflow:', error);
            this.availableWorkflows = [];
            this.schemasLoaded = true;
        } finally {
            this._isLoadingWorkflows = false;
        }
    }

    /**
     * Create unique fallback title for workflows when schema loading fails
     */
    createFallbackTitle(workflowName) {
        // Convert workflow name to a readable title
        const title = workflowName
            .replace(/_/g, ' ')
            .replace(/\b\w/g, l => l.toUpperCase());
        
        // Add specific suffixes for known workflows
        if (workflowName.includes('copy')) {
            return title;
        } else if (workflowName === 'bike_insights') {
            return 'Bike Insights Original';
        }
        
        return title;
    }

    /**
     * Fetch schema from local files with caching
     */
    async fetchSchema(workflowName) {
        if (this.schemaCache[workflowName]) {
            return this.schemaCache[workflowName];
        }
        // Try to load from API first
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
                throw new Error(`API HTTP error! status: ${response.status}`);
            }
            const schema = await response.json();
            this.schemaCache[workflowName] = schema;
            console.log(`Successfully loaded schema for ${workflowName} from API`);
            return schema;
        } catch (apiError) {
            console.error(`Failed to fetch schema for ${workflowName} from API:`, apiError);
            // Fallback to local file if API fails
            try {
                const response = await fetch(`../schema/${workflowName}.json`);
                if (!response.ok) {
                    throw new Error(`HTTP error! status: ${response.status}`);
                }
                const schema = await response.json();
                this.schemaCache[workflowName] = schema;
                console.log(`Successfully loaded schema for ${workflowName} from local file`);
                return schema;
            } catch (error) {
                console.error(`Failed to fetch schema for ${workflowName} from local file:`, error);
                throw new Error(`Schema fetch failed from both API and local file: ${workflowName}`);
            }
        }
    }

    /**
     * Select and load a schema
     */
    async selectSchema(schemaName) {
        this.currentSchema = schemaName;
        await this.loadSchemaForm(schemaName);
        this.resetFormData();
    }

    /**
     * Load schema form and generate UI
     */
    async loadSchemaForm(schemaName) {
        try {
            const schema = await this.fetchSchema(schemaName);
            const rootModel = schema.schemas.RootModel;
            
            // CRITICAL: Store the currentSchemaData for use by JSONResponseBuilder
            this.currentSchemaData = rootModel;
            console.log('✅ Set currentSchemaData for dynamic extraction:', this.currentSchemaData);
            
            this.showFormHeader = true;
            this.showFormActions = true;
            
            this.formTitle = this.getSchemaTitle(rootModel, schemaName);
            
            // Use form generation to create the form HTML
            const formHtml = this.generateFormFromSchema(rootModel, schema.schemas);
            this.dynamicFormHtml = formHtml;
            
            this.initializeFormData(rootModel);
            
            // Auto-add first array items after DOM update
            setTimeout(async () => {
                await this.autoAddFirstArrayItems(rootModel);
            }, 50);
        } catch (error) {
            console.error('Failed to load schema form:', error);
            this.dynamicFormHtml = `
                <div class="text-center py-5">
                    <div class="alert alert-info border-0" style="background-color: #f8f9fa;">
                        <h5 class="text-danger mb-2">Not Found</h5>
                        <p class="text-muted mb-0">
                            Please check the workflow schema configuration.
                        </p>
                    </div>
                </div>
            `;
        }
    }

    /**
     * Auto-add first array items for required arrays
     */
    async autoAddFirstArrayItems(rootModel) {
        if (this.arrayManager) {
            await this.arrayManager.autoAddFirstArrayItems(this.currentSchema, rootModel);
        }
    }

    /**
     * Generate form HTML from schema
     */
    generateFormFromSchema(model, allSchemas) {
        if (!model.properties) return '';
        let formHtml = '';
        const displayOrder = model.ui_metadata?.display_order || Object.keys(model.properties);
        for (const fieldName of displayOrder) {
            const field = model.properties[fieldName];
            if (field) {
                formHtml += this.generateFieldHtml(fieldName, field, allSchemas);
            }
        }
        return formHtml;
    }

    /**
     * Generate HTML for individual field
     */
    generateFieldHtml(fieldName, field, allSchemas) {
        const rawDisplayName = field.display_name || field.title || fieldName;
        const displayName = BaseManager.cleanDisplayName(rawDisplayName);
        const fieldId = `field-${fieldName}`;
        
        console.log(`🔧 DynamicWorkflow: Generating field: ${fieldName} (${displayName}), type: ${field.type}, ui_component: ${field.ui_component}`);
        
        // Always prioritize $ref object references over ui_component
        if (field.$ref) {
            return this.generateNestedObjectField(fieldName, field, allSchemas);
        }
        
        switch (field.ui_component) {
            case 'text_input':
                return `
                    <div class="mb-3">
                        <label class="form-label" for="${fieldId}">${displayName}</label>
                        <input type="text" class="form-control" id="${fieldId}" 
                               placeholder="Enter ${displayName.toLowerCase()}"
                               onchange="window.dynamicWorkflow.updateFormData('${fieldName}', this.value)"
                               oninput="window.dynamicWorkflow.updateFormData('${fieldName}', this.value)">
                    </div>
                `;
            case 'number_input':
                const numConf = field.number_config || {};
                return `
                    <div class="mb-3">
                        <label class="form-label" for="${fieldId}">${displayName}</label>
                        <input type="number" class="form-control" id="${fieldId}"
                               min="${numConf.min || ''}" max="${numConf.max || ''}" step="${numConf.step || 1}"
                               placeholder="Enter ${displayName.toLowerCase()}"
                               onchange="window.dynamicWorkflow.updateFormData('${fieldName}', parseFloat(this.value) || 0)"
                               oninput="window.dynamicWorkflow.updateFormData('${fieldName}', parseFloat(this.value) || 0)">
                    </div>
                `;
            case 'array':
                return this.generateArrayField(fieldName, field, allSchemas);
            case 'union_select':
                return this.generateUnionSelectField(fieldName, field, allSchemas);
            default:
                return `
                    <div class="mb-3">
                        <label class="form-label" for="${fieldId}">${displayName}</label>
                        <input type="text" class="form-control" id="${fieldId}"
                               placeholder="Enter ${displayName.toLowerCase()}"
                               onchange="window.dynamicWorkflow.updateFormData('${fieldName}', this.value)"
                               oninput="window.dynamicWorkflow.updateFormData('${fieldName}', this.value)">
                    </div>
                `;
        }
    }

    /**
     * Generate array field (delegate to ArrayManager)
     */
    generateArrayField(fieldName, field, allSchemas) {
        if (this.arrayManager) {
            return this.arrayManager.generateArrayField(this.currentSchema, fieldName, field);
        }
        return `<div class="alert alert-warning">Array field generation not available</div>`;
    }

    /**
     * Generate nested object field
     */
    generateNestedObjectField(fieldName, field, allSchemas) {
        const rawDisplayName = field.display_name || field.title || fieldName;
        const displayName = BaseManager.cleanDisplayName(rawDisplayName);
        const fieldId = `nested-${fieldName}`;
        
        // Resolve the $ref to get the referenced schema
        const schemaRef = field.$ref;
        if (!schemaRef) {
            console.error(`No $ref found for nested object field: ${fieldName}`);
            return this.generateFallbackField(fieldName, field);
        }
        
        const schemaName = schemaRef.split('/').pop();
        const referencedSchema = allSchemas[schemaName] || 
                               allSchemas.RootModel?.definitions?.[schemaName] ||
                               this.schemaCache[this.currentSchema]?.schemas?.RootModel?.definitions?.[schemaName];
        
        if (!referencedSchema) {
            console.error(`Referenced schema not found: ${schemaName}`);
            return this.generateFallbackField(fieldName, field);
        }
        
        // Generate nested fields HTML
        let nestedFieldsHtml = '';
        if (referencedSchema.properties) {
            const displayOrder = referencedSchema.ui_metadata?.display_order || Object.keys(referencedSchema.properties);
            for (const propName of displayOrder) {
                const prop = referencedSchema.properties[propName];
                if (prop) {
                    nestedFieldsHtml += this.generateNestedObjectFieldHtml(fieldName, propName, prop);
                }
            }
        }
        
        return `
            <div class="card mb-4">
                <div class="card-body">
                    <div class="nested-object-header" id="${fieldId}-header">
                        <div class="form-label">${displayName}</div>
                        <button class="toggle-button" type="button" onclick="window.dynamicWorkflow.toggleNestedObjectField('${fieldId}')" aria-label="Toggle ${displayName}">
                            ▼
                        </button>
                    </div>
                    <div class="nested-object-fields" id="${fieldId}-content">
                        ${nestedFieldsHtml}
                    </div>
                </div>
            </div>
        `;
    }

    /**
     * Generate HTML for nested object field
     */
    generateNestedObjectFieldHtml(parentFieldName, propName, prop) {
        const rawDisplayName = prop.display_name || prop.title || propName;
        const displayName = BaseManager.cleanDisplayName(rawDisplayName);
        const fieldId = `${parentFieldName}-${propName}`;
        const onChange = `onchange="window.dynamicWorkflow.updateNestedObjectFieldData('${parentFieldName}', '${propName}', this.value)"`;
        const onChangeFloat = `onchange="window.dynamicWorkflow.updateNestedObjectFieldData('${parentFieldName}', '${propName}', parseFloat(this.value))"`;

        switch (prop.type) {
            case 'number':
                const numConf = prop.number_config || {};
                return `
                    <div class="mb-3">
                        <label class="form-label" for="${fieldId}">${displayName}</label>
                        <input type="number" class="form-control" id="${fieldId}"
                               min="${numConf.min || ''}" max="${numConf.max || ''}" step="${numConf.step || 0.01}"
                               placeholder="Enter ${displayName.toLowerCase()}" ${onChangeFloat}>
                        ${prop.description ? `<div class="form-text">${prop.description}</div>` : ''}
                    </div>
                `;
            case 'integer':
                return `
                    <div class="mb-3">
                        <label class="form-label" for="${fieldId}">${displayName}</label>
                        <input type="number" class="form-control" id="${fieldId}"
                               step="1" placeholder="Enter ${displayName.toLowerCase()}" ${onChangeFloat}>
                        ${prop.description ? `<div class="form-text">${prop.description}</div>` : ''}
                    </div>
                `;
            default:
                return `
                    <div class="mb-3">
                        <label class="form-label" for="${fieldId}">${displayName}</label>
                        <input type="text" class="form-control" id="${fieldId}"
                               placeholder="Enter ${displayName.toLowerCase()}" ${onChange}>
                        ${prop.description ? `<div class="form-text">${prop.description}</div>` : ''}
                    </div>
                `;
        }
    }

    /**
     * Generate fallback field
     */
    generateFallbackField(fieldName, field) {
        const rawDisplayName = field.display_name || field.title || fieldName;
        const displayName = BaseManager.cleanDisplayName(rawDisplayName);
        const fieldId = `field-${fieldName}`;
        return `
            <div class="mb-3">
                <label class="form-label" for="${fieldId}">${displayName}</label>
                <input type="text" class="form-control" id="${fieldId}"
                       placeholder="Enter ${displayName.toLowerCase()}"
                       onchange="window.dynamicWorkflow.updateFormData('${fieldName}', this.value)">
                <div class="form-text text-warning">Unable to resolve nested object schema</div>
            </div>
        `;
    }

    /**
     * Generate union select field
     */
    generateUnionSelectField(fieldName, field, allSchemas) {
        const rawDisplayName = field.display_name || field.title || fieldName;
        const displayName = BaseManager.cleanDisplayName(rawDisplayName);
        const unionOptions = field.union_options || [];
        
        // Cache the field and union options for dynamic rendering
        this.fieldCache[`${this.currentSchema}_${fieldName}_union`] = {
            field: field,
            unionOptions: unionOptions,
            allSchemas: allSchemas
        };
        
        let optionsHtml = unionOptions.map(option => `
            <div class="option-card" onclick="window.dynamicWorkflow.selectUnionOption('${fieldName}', '${option.value}', this)">
                <span class="option-name">${BaseManager.cleanDisplayName(option.label)}</span>
            </div>
        `).join('');

        return `
            <div class="form-group">
                <label class="form-label">${displayName}</label>
                <div class="option-selection" id="union-${fieldName}">${optionsHtml}</div>
                <div id="union-fields-${fieldName}" class="union-fields-container mt-3"></div>
            </div>
        `;
    }

    /**
     * Get union icon
     */
    getUnionIcon(label) {
        return '🔧';
    }

    /**
     * Get schema title
     */
    getSchemaTitle(schema, workflowName) {
        if (schema.title && schema.title !== 'RootModel') {
            return schema.title;
        }
        return workflowName.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase());
    }

    /**
     * Update form data (delegate to DataManager)
     */
    updateFormData(fieldName, value) {
        if (this.dataManager) {
            this.dataManager.updateFormData(this.currentSchema, fieldName, value);
        }
    }

    /**
     * Initialize form data (delegate to DataManager)
     */
    initializeFormData(model) {
        if (this.dataManager) {
            this.dataManager.initializeFormData(this.currentSchema, model);
        }
    }

    /**
     * Reset form data (delegate to DataManager)
     */
    resetFormData() {
        if (this.dataManager) {
            this.dataManager.resetFormData(this.currentSchema);
        }
        
        setTimeout(() => {
            document.querySelectorAll('.form-input').forEach(input => input.value = '');
            document.querySelectorAll('.option-card.selected').forEach(card => card.classList.remove('selected'));
        }, 50);
    }

    /**
     * Get form data for schema (delegate to DataManager with DOM fallback)
     */
    getFormDataForSchema() {
        if (this.dataManager) {
            // Get stored data from DataManager
            let storedData = this.dataManager.getFormDataForSchema(this.currentSchema);
            
            // If stored data is empty, try to collect from DOM
            if (!storedData || Object.keys(storedData).length === 0) {
                storedData = this.collectFormDataFromDOM();
            }
            
            return storedData;
        }
        
        // Fallback: collect directly from DOM if DataManager not available
        return this.collectFormDataFromDOM();
    }

    /**
     * Collect current form data directly from DOM elements
     */
    collectFormDataFromDOM() {
        const formData = {};
        
        try {
            // Collect data from text and number inputs (including empty values)
            const inputs = document.querySelectorAll('#dynamicFormsContainer input, #dynamicFormsContainer select, #dynamicFormsContainer textarea');
            inputs.forEach(input => {
                if (input.id) {
                    // Parse field name from input ID
                    const fieldName = this.parseFieldNameFromId(input.id);
                    if (fieldName) {
                        // Convert value based on input type
                        let value = input.value;
                        if (input.type === 'number' && value !== '') {
                            value = parseFloat(value) || 0;
                        }
                        
                        // Only set non-empty values or explicitly capture empty strings for required fields
                        if (value !== '' || input.hasAttribute('required')) {
                            // Handle nested field names (e.g., "parent-child" becomes nested object)
                            this.setNestedValue(formData, fieldName, value);
                        }
                    }
                }
            });
            
            // Collect data from selected union options
            const selectedOptions = document.querySelectorAll('#dynamicFormsContainer .option-card.selected');
            selectedOptions.forEach(option => {
                const parentContainer = option.closest('.form-group');
                if (parentContainer) {
                    const label = parentContainer.querySelector('.form-label');
                    if (label) {
                        const fieldName = this.sanitizeFieldName(label.textContent);
                        const optionName = option.querySelector('.option-name');
                        if (optionName) {
                            formData[fieldName] = optionName.textContent.trim();
                        }
                    }
                }
            });
            
            // Collect data from array items
            const arrayContainers = document.querySelectorAll('#dynamicFormsContainer .array-container');
            arrayContainers.forEach(container => {
                const arrayFieldName = this.extractArrayFieldName(container);
                if (arrayFieldName) {
                    const items = container.querySelectorAll('.array-item');
                    const arrayData = [];
                    
                    items.forEach((item, index) => {
                        const itemData = {};
                        const itemInputs = item.querySelectorAll('input, select, textarea');
                        itemInputs.forEach(input => {
                            if (input.id && input.value !== '') {
                                const propName = this.extractArrayItemPropName(input.id);
                                if (propName) {
                                    let value = input.value;
                                    if (input.type === 'number') {
                                        value = parseFloat(value) || 0;
                                    }
                                    itemData[propName] = value;
                                }
                            }
                        });
                        
                        if (Object.keys(itemData).length > 0) {
                            arrayData.push(itemData);
                        }
                    });
                    
                    if (arrayData.length > 0) {
                        formData[arrayFieldName] = arrayData;
                    }
                }
            });
            
            console.log('DynamicWorkflowManager: Enhanced form data collection from DOM:', formData);
            
        } catch (error) {
            console.error('Error collecting form data from DOM:', error);
        }
        
        return formData;
    }

    /**
     * Parse field name from DOM element ID
     */
    parseFieldNameFromId(elementId) {
        return BaseManager.parseFieldNameFromId(elementId);
    }

    /**
     * Sanitize field name from label text
     */
    sanitizeFieldName(labelText) {
        return BaseManager.sanitizeFieldName(labelText);
    }

    /**
     * Extract array field name from container element
     */
    extractArrayFieldName(container) {
        // Look for data attributes or class names that indicate the field name
        const fieldName = container.getAttribute('data-field-name') || 
                         container.getAttribute('data-array-field') ||
                         container.id?.replace('array-', '') ||
                         null;
        
        if (!fieldName) {
            // Try to extract from the nearest label
            const label = container.closest('.form-group')?.querySelector('.form-label');
            if (label) {
                return this.sanitizeFieldName(label.textContent);
            }
        }
        
        return fieldName;
    }

    /**
     * Extract property name from array item input ID
     */
    extractArrayItemPropName(inputId) {
        // Pattern: "arrayField-itemIndex-propName"
        const parts = inputId.split('-');
        if (parts.length >= 3) {
            // Find the numeric index and take everything after it
            const numberIndex = parts.findIndex(part => /^\d+$/.test(part));
            if (numberIndex >= 0 && numberIndex < parts.length - 1) {
                return parts.slice(numberIndex + 1).join('_');
            }
        }
        
        // Fallback: take the last part
        return parts[parts.length - 1];
    }

    /**
     * Set nested value in object using dot notation
     */
    setNestedValue(obj, path, value) {
        const keys = path.split('.');
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

    /**
     * Update nested object field data (delegate to DataManager)
     */
    updateNestedObjectFieldData(parentFieldName, propName, value) {
        if (this.dataManager) {
            this.dataManager.updateNestedObjectFieldData(this.currentSchema, parentFieldName, propName, value);
        }
    }

    /**
     * Update union field data (delegate to DataManager)
     */
    updateUnionFieldData(parentFieldName, propName, value) {
        if (this.dataManager) {
            this.dataManager.updateUnionFieldData(this.currentSchema, parentFieldName, propName, value);
        }
    }

    /**
     * Select union option
     */
    async selectUnionOption(fieldName, value, element) {
        element.parentNode.querySelectorAll('.option-card').forEach(card => card.classList.remove('selected'));
        element.classList.add('selected');
        this.updateFormData(fieldName, value);
        
        // Render dynamic fields for the selected union option
        await this.renderUnionFields(fieldName, value);
    }

    /**
     * Render dynamic fields for selected union option
     */
    async renderUnionFields(fieldName, selectedValue) {
        try {
            const fieldKey = `${this.currentSchema}_${fieldName}_union`;
            const cachedData = this.fieldCache[fieldKey];
            if (!cachedData) {
                console.error(`Union field data not found for: ${fieldKey}`);
                return;
            }

            const { unionOptions, allSchemas } = cachedData;
            const selectedOption = unionOptions.find(option => option.value === selectedValue);
            if (!selectedOption) {
                console.error(`Selected union option not found: ${selectedValue}`);
                return;
            }

            // Get the schema for the selected union type
            const schemaRef = selectedOption.schema_ref;
            if (!schemaRef) {
                console.error(`Schema reference not found for union option: ${selectedValue}`);
                return;
            }

            const schemaName = schemaRef.split('/').pop();
            const selectedSchema = allSchemas[schemaName] || 
                                allSchemas.RootModel?.definitions?.[schemaName] ||
                                this.schemaCache[this.currentSchema]?.schemas?.RootModel?.definitions?.[schemaName];

            if (!selectedSchema) {
                console.error(`Schema not found for: ${schemaName}`);
                return;
            }

            // Clear previous union fields
            const container = document.getElementById(`union-fields-${fieldName}`);
            if (container) {
                container.innerHTML = '';
            }

            // Generate fields HTML for the selected schema
            const fieldsHtml = this.generateUnionSchemaFields(fieldName, selectedSchema, allSchemas);
            if (container) {
                container.innerHTML = fieldsHtml;
            }

            // Initialize form data for the selected union type
            this.initializeUnionFormData(fieldName, selectedSchema);

        } catch (error) {
            console.error('Failed to render union fields:', error);
        }
    }

    /**
     * Generate HTML for union schema fields
     */
    generateUnionSchemaFields(parentFieldName, schema, allSchemas) {
        if (!schema.properties) return '';
        
        let fieldsHtml = '<div class="union-schema-fields mt-3 p-3" style="border: 1px solid var(--bs-border-color); border-radius: 6px; background-color: #f8f9fa;">';
        
        const displayOrder = schema.ui_metadata?.display_order || Object.keys(schema.properties);
        for (const propName of displayOrder) {
            const prop = schema.properties[propName];
            if (prop) {
                fieldsHtml += this.generateUnionFieldHtml(parentFieldName, propName, prop);
            }
        }
        
        fieldsHtml += '</div>';
        return fieldsHtml;
    }

    /**
     * Generate HTML for individual union field
     */
    generateUnionFieldHtml(parentFieldName, propName, prop) {
        const displayName = prop.display_name || prop.title || propName;
        const fieldId = `${parentFieldName}-${propName}`;
        const onChange = `onchange="window.dynamicWorkflow.updateUnionFieldData('${parentFieldName}', '${propName}', this.value)"`;
        const onChangeFloat = `onchange="window.dynamicWorkflow.updateUnionFieldData('${parentFieldName}', '${propName}', parseFloat(this.value))"`;

        switch (prop.type) {
            case 'number':
                const numConf = prop.number_config || {};
                return `
                    <div class="mb-3">
                        <label class="form-label" for="${fieldId}">${displayName}</label>
                        <input type="number" class="form-control" id="${fieldId}"
                               min="${numConf.min || ''}" max="${numConf.max || ''}" step="${numConf.step || 0.01}"
                               placeholder="Enter ${displayName.toLowerCase()}" ${onChangeFloat}>
                        ${prop.description ? `<div class="form-text">${prop.description}</div>` : ''}
                    </div>
                `;
            case 'integer':
                return `
                    <div class="mb-3">
                        <label class="form-label" for="${fieldId}">${displayName}</label>
                        <input type="number" class="form-control" id="${fieldId}"
                               step="1" placeholder="Enter ${displayName.toLowerCase()}" ${onChangeFloat}>
                        ${prop.description ? `<div class="form-text">${prop.description}</div>` : ''}
                    </div>
                `;
            default:
                return `
                    <div class="mb-3">
                        <label class="form-label" for="${fieldId}">${displayName}</label>
                        <input type="text" class="form-control" id="${fieldId}"
                               placeholder="Enter ${displayName.toLowerCase()}" ${onChange}>
                        ${prop.description ? `<div class="form-text">${prop.description}</div>` : ''}
                    </div>
                `;
        }
    }

    /**
     * Initialize union form data (delegate to DataManager)
     */
    initializeUnionFormData(fieldName, schema) {
        if (this.dataManager) {
            this.dataManager.initializeUnionFormData(this.currentSchema, fieldName, schema);
        }
    }

    /**
     * Add entity (delegate to ArrayManager)
     */
    async addEntity() {
        if (this.arrayManager) {
            await this.arrayManager.addEntity(this.currentSchema);
        } else {
            alert('Array manager not available');
        }
    }

    /**
     * Process workflow data
     */
    processData() {
        if (!this.currentSchema || !Object.keys(this.getFormDataForSchema()).length) {
            alert('Please select a schema and enter some data first');
            return;
        }
        
        this.showResults = true;
        const results = this.generateSchemaResults();
        this.displayResults(results);
        
        setTimeout(() => {
            document.querySelector('[x-show="showResults"]')?.scrollIntoView({ behavior: 'smooth' });
        }, 100);
    }

    /**
     * Generate schema processing results
     */
    generateSchemaResults() {
        const data = this.getFormDataForSchema();
        const dataKeys = Object.keys(data);
        return {
            summary: {
                schema: this.currentSchema,
                fieldsCompleted: dataKeys.length,
                dataEntries: JSON.stringify(data, null, 2)
            },
            insights: [
                `Using schema: <strong>${this.currentSchema}</strong>`,
                `Completed <strong>${dataKeys.length}</strong> top-level form fields.`,
                'Data structure follows the selected API-driven schema format.',
                'Form data is ready for processing or export.'
            ]
        };
    }

    /**
     * Display processing results
     */
    displayResults(results) {
        const dataStr = results.summary.dataEntries;
        this.resultsHtml = `
            <div style="margin-bottom: 2rem;">
                <h4 style="color: #333; margin-bottom: 1rem;">📊 Processing Summary</h4>
                <ul style="list-style: none; padding: 0;">
                    ${results.insights.map(insight => `
                        <li style="padding: 0.5rem 0; border-bottom: 1px solid #f0f0f0;">
                            <span style="color: var(--primary-blue); margin-right: 0.5rem;">•</span>
                            ${insight}
                        </li>
                    `).join('')}
                </ul>
            </div>
            <div>
                <h4 style="color: #333; margin-bottom: 1rem;">📋 Submitted Data (JSON)</h4>
                <pre style="background-color: #f8f9fa; padding: 1rem; border-radius: 6px; border: 1px solid var(--border-color); white-space: pre-wrap; word-wrap: break-word;"><code>${dataStr}</code></pre>
            </div>
        `;
    }

    /**
     * Export workflow data
     */
    exportData() {
        if (!this.currentSchema || !Object.keys(this.getFormDataForSchema()).length) {
            alert('No data to export. Please fill out the form first.');
            return;
        }
        
        if (this.dataManager) {
            try {
                const exportResult = this.dataManager.exportData(this.currentSchema, 'json');
                this.downloadFile(exportResult.content, exportResult.filename, exportResult.mimeType);
            } catch (error) {
                console.error('Export failed:', error);
                alert('Export failed: ' + error.message);
            }
        }
    }

    /**
     * Download file utility
     */
    downloadFile(content, filename, mimeType) {
        const dataBlob = new Blob([content], {type: mimeType});
        const link = document.createElement('a');
        link.href = URL.createObjectURL(dataBlob);
        link.download = filename;
        link.click();
    }

    /**
     * Reset all workflow data
     */
    resetAll() {
        if (confirm('Are you sure you want to reset all data? This action cannot be undone.')) {
            if (this.dataManager) {
                this.dataManager.clearAll();
            }
            
            this.currentSchema = null;
            this.dynamicFormHtml = '';
            this.resultsHtml = '';
            this.showFormHeader = false;
            this.showFormActions = false;
            this.showResults = false;
        }
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
            // Expand
            content.classList.remove('collapsed');
            toggleButton.classList.remove('collapsed');
            toggleButton.innerHTML = '▼';
            toggleButton.setAttribute('aria-expanded', 'true');
        } else {
            // Collapse
            content.classList.add('collapsed');
            toggleButton.classList.add('collapsed');
            toggleButton.innerHTML = '▶';
            toggleButton.setAttribute('aria-expanded', 'false');
        }
        
        console.log(`DynamicWorkflowManager: Toggled ${fieldId} - ${isCollapsed ? 'expanded' : 'collapsed'}`);
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
            // Expand
            content.classList.remove('collapsed');
            toggleButton.classList.remove('collapsed');
            toggleButton.innerHTML = '▼';
            toggleButton.setAttribute('aria-expanded', 'true');
        } else {
            // Collapse
            content.classList.add('collapsed');
            toggleButton.classList.add('collapsed');
            toggleButton.innerHTML = '▶';
            toggleButton.setAttribute('aria-expanded', 'false');
        }
        
        console.log(`DynamicWorkflowManager: Toggled union ${fieldId} - ${isCollapsed ? 'expanded' : 'collapsed'}`);
    }

    /**
     * Bulk toggle all sections
     */
    bulkToggleSections(action = 'toggle') {
        // Toggle array items via ArrayManager
        if (this.arrayManager) {
            this.arrayManager.bulkToggleArrayItems(action);
        }

        // Toggle nested objects
        const nestedObjects = document.querySelectorAll('[id^="nested-"][id$="-content"]');
        nestedObjects.forEach(content => {
            const fieldId = content.id.replace('-content', '');
            const toggleButton = document.querySelector(`#${fieldId}-header .toggle-button`);
            
            if (!toggleButton) return;
            
            const isCurrentlyCollapsed = content.classList.contains('collapsed');
            
            switch (action) {
                case 'expand':
                    if (isCurrentlyCollapsed) {
                        this.toggleNestedObjectField(fieldId);
                    }
                    break;
                case 'collapse':
                    if (!isCurrentlyCollapsed) {
                        this.toggleNestedObjectField(fieldId);
                    }
                    break;
                case 'toggle':
                default:
                    this.toggleNestedObjectField(fieldId);
                    break;
            }
        });
        
        // Toggle union fields
        const unionFields = document.querySelectorAll('[id^="union-fields-"]');
        unionFields.forEach(content => {
            const fieldId = content.id.replace('union-fields-', '').replace('-fields', '');
            const toggleButton = document.querySelector(`#union-${fieldId}-header .toggle-button`);
            
            if (!toggleButton) return;
            
            const isCurrentlyCollapsed = content.classList.contains('collapsed');
            
            switch (action) {
                case 'expand':
                    if (isCurrentlyCollapsed) {
                        this.toggleUnionFields(`union-${fieldId}`);
                    }
                    break;
                case 'collapse':
                    if (!isCurrentlyCollapsed) {
                        this.toggleUnionFields(`union-${fieldId}`);
                    }
                    break;
                case 'toggle':
                default:
                    this.toggleUnionFields(`union-${fieldId}`);
                    break;
            }
        });
        
        console.log(`DynamicWorkflowManager: Bulk ${action} performed on all sections`);
    }

    /**
     * Get current workflow state
     */
    getCurrentState() {
        return {
            currentSchema: this.currentSchema,
            availableWorkflows: this.availableWorkflows,
            schemasLoaded: this.schemasLoaded,
            showFormHeader: this.showFormHeader,
            showFormActions: this.showFormActions,
            showResults: this.showResults,
            formTitle: this.formTitle,
            formData: this.getFormDataForSchema()
        };
    }
}

// Create global instance and initialize
window.dynamicWorkflow = new DynamicWorkflowManager();

// Auto-initialize when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    if (window.dynamicWorkflow) {
        window.dynamicWorkflow.init();
    }
});

// Export for use in other modules
window.DynamicWorkflowManager = DynamicWorkflowManager;