/**
 * Prompt Evaluation Core - Business Logic
 * Contains all the complex business logic and data processing functions
 */

/**
 * Core functionality class for Prompt Evaluation
 * Contains all the large/complex functions moved from inline HTML
 */
class PromptEvaluationCore {
    /**
     * Initialize the application
     */
    static async initialize(app) {
        console.log('Enhanced Prompt Evaluation App initialized');
        const params = new URLSearchParams(window.location.search);
    // Only accept `id` as the query parameter
    app.workflowQueryParam = params.get('id');
        
        await app.waitForDynamicWorkflow();
        app.setupStateSync();
        
        if (window.dynamicWorkflow) {
            await window.dynamicWorkflow.init();
            app.syncState();
            
            // Auto-select workflow if specified in query param
            if (app.workflowQueryParam && app.currentSchema !== app.workflowQueryParam) {
                const trySelect = async () => {
                    if (window.dynamicWorkflow.availableWorkflows?.length) {
                        if (window.dynamicWorkflow.currentSchema !== app.workflowQueryParam) {
                            await window.dynamicWorkflow.selectSchema(app.workflowQueryParam);
                            app.syncState();
                        }
                    } else {
                        setTimeout(trySelect, 100);
                    }
                };
                trySelect();
            }
        }
        
        await app.loadRevisionsFromAPI();
        app.initializePromptVersion();
        app.initFormDataTracking();
    }

    /**
     * Wait for dynamic workflow to be fully ready
     */
    static async waitForDynamicWorkflow() {
        let attempts = 0;
        const maxAttempts = 50; // 5 seconds max wait time
        
        while (attempts < maxAttempts) {
            if (window.dynamicWorkflow && 
                typeof window.dynamicWorkflow.collectFormDataFromDOM === 'function' &&
                typeof window.dynamicWorkflow.getFormDataForSchema === 'function') {
                console.log('DynamicWorkflow is ready after', attempts * 100, 'ms');
                return;
            }
            
            await new Promise(resolve => setTimeout(resolve, 100));
            attempts++;
        }
        
        console.warn('DynamicWorkflow initialization timeout - proceeding with limited functionality');
    }

    /**
     * Setup state synchronization
     */
    static setupStateSync(app) {
        // Sync state every 200ms to ensure Alpine.js stays updated
        setInterval(() => {
            app.syncState();
        }, 200);
    }

    /**
     * Extract schema information for dynamic transformation
     */
    static getSchemaInfo(app) {
        try {
            console.log('=== getSchemaInfo DEBUG ===');
            console.log('window.dynamicWorkflow exists:', !!window.dynamicWorkflow);
            console.log('currentSchemaData exists:', !!window.dynamicWorkflow?.currentSchemaData);
            console.log('currentSchema:', app.currentSchema);
            
            // Method 1: Try to get from currentSchemaData and build proper schema object
            if (window.dynamicWorkflow?.currentSchemaData) {
                const currentSchemaData = window.dynamicWorkflow.currentSchemaData;
                console.log('currentSchemaData structure:', currentSchemaData);
                
                // Build the expected schema object structure
                const fullSchemaObject = {
                    workflow_name: app.currentSchema || 'unknown',
                    schemas: {
                        RootModel: currentSchemaData
                    }
                };
                
                console.log('✅ Built full schema object:', fullSchemaObject);
                
                // Use JSONResponseBuilder to extract info dynamically
                try {
                    const schemaInfo = JSONResponseBuilder.extractSchemaInfo(fullSchemaObject);
                    console.log('✅ Successfully extracted dynamic schema info:', schemaInfo);
                    
                    return {
                        containerName: schemaInfo.containerName,
                        arrayFieldPatterns: schemaInfo.arrayFieldPatterns,
                        fieldHierarchy: schemaInfo.fieldHierarchy,
                        dynamicPatterns: schemaInfo.dynamicPatterns,
                        schema: fullSchemaObject
                    };
                } catch (extractError) {
                    console.warn('Dynamic extraction failed, trying alternative methods:', extractError);
                }
            }
            
            // Method 2: Try to get from schema cache
            if (window.dynamicWorkflow?.schemaCache && app.currentSchema) {
                const cachedSchema = window.dynamicWorkflow.schemaCache[app.currentSchema];
                if (cachedSchema) {
                    console.log('✅ Using cached schema:', cachedSchema);
                    
                    try {
                        const schemaInfo = JSONResponseBuilder.extractSchemaInfo(cachedSchema);
                        console.log('✅ Successfully extracted from cached schema:', schemaInfo);
                        
                        return {
                            containerName: schemaInfo.containerName,
                            arrayFieldPatterns: schemaInfo.arrayFieldPatterns,
                            fieldHierarchy: schemaInfo.fieldHierarchy,
                            dynamicPatterns: schemaInfo.dynamicPatterns,
                            schema: cachedSchema
                        };
                    } catch (cacheError) {
                        console.warn('Cached schema extraction failed:', cacheError);
                    }
                }
            }
            
            // Method 3: Use schema name to let JSONResponseBuilder handle it
            if (app.currentSchema) {
                console.log('⚠️ Falling back to schema name only, letting JSONResponseBuilder handle loading');
                
                try {
                    // Let JSONResponseBuilder attempt to extract from cached data
                    const containerName = JSONResponseBuilder.extractContainerFieldName(null, app.currentSchema);
                    
                    return {
                        containerName: containerName,
                        arrayFieldPatterns: [containerName], // Basic fallback
                        fieldHierarchy: {},
                        dynamicPatterns: [],
                        schema: null
                    };
                } catch (nameError) {
                    console.error('Schema name fallback failed:', nameError);
                }
            }
            
            console.log('=== END getSchemaInfo DEBUG ===');
            
            // Last resort: This should not happen if everything is working correctly
            console.error('❌ All schema info extraction methods failed');
            throw new Error('Cannot extract schema information - no valid schema data available');
            
        } catch (error) {
            console.error('Error in getSchemaInfo:', error);
            throw new Error(`Schema info extraction failed: ${error.message}`);
        }
    }

    /**
     * Load schema directly from schema file (fallback method) - DEPRECATED
     * This method should no longer be used as all schema info should be extracted dynamically
     */
    static loadSchemaFromFile(schemaName) {
        console.error('⚠️ loadSchemaFromFile called - this method is deprecated and should not be used');
        console.error('Schema loading should be handled dynamically through JSONResponseBuilder.extractContainerFieldName');
        throw new Error(`Deprecated method loadSchemaFromFile called for schema: ${schemaName}`);
    }

    /**
     * Extract array field patterns from schema definitions
     * This identifies field prefixes that should be cleaned up during transformation
     */
    static extractArrayFieldPatterns(schema) {
        const patterns = [];
        
        try {
            // Look through all schema definitions for array fields
            if (schema.definitions || schema.$defs) {
                const definitions = schema.definitions || schema.$defs;
                
                Object.keys(definitions).forEach(defKey => {
                    const definition = definitions[defKey];
                    if (definition.properties) {
                        Object.keys(definition.properties).forEach(propKey => {
                            const property = definition.properties[propKey];
                            
                            // If this property is an array, add its name to patterns
                            if (property.type === 'array') {
                                patterns.push(propKey);
                            }
                        });
                    }
                });
            }
            
            // Also check the root schema properties for arrays
            if (schema.properties) {
                Object.keys(schema.properties).forEach(propKey => {
                    const property = schema.properties[propKey];
                    if (property.type === 'array') {
                        patterns.push(propKey);
                    }
                });
            }
            
            console.log('Extracted array field patterns from schema:', patterns);
            
        } catch (error) {
            console.error('Error extracting array field patterns:', error);
        }
        
        return patterns.length > 0 ? patterns : ['bike_sales', 'laptop_sales']; // fallback
    }

    /**
     * Synchronize state with modular classes
     */
    static syncState(app) {
        if (window.dynamicWorkflow) {
            app.availableWorkflows = [...(window.dynamicWorkflow.availableWorkflows || [])];
            app.schemasLoaded = window.dynamicWorkflow.schemasLoaded || false;
            app.currentSchema = window.dynamicWorkflow.currentSchema || null;
            app.showFormHeader = window.dynamicWorkflow.showFormHeader || false;
            app.showFormActions = window.dynamicWorkflow.showFormActions || false;
            app.showResults = window.dynamicWorkflow.showResults || false;
            app.formTitle = window.dynamicWorkflow.formTitle || 'Dynamic Form';
            app.dynamicFormHtml = window.dynamicWorkflow.dynamicFormHtml || '';
            app.resultsHtml = window.dynamicWorkflow.resultsHtml || '';
            
            // Update workflow name for header
            if (app.currentSchema) {
                const selectedWorkflow = app.availableWorkflows.find(w => w.name === app.currentSchema);
                if (selectedWorkflow) {
                    app.workflow = { 
                        name: selectedWorkflow.title, 
                        id: selectedWorkflow.name 
                    };
                }
            }
        }
    }

    /**
     * Console logging functionality
     */
    static constructRawJson(app) {
        app.forceDataSync();
        
        const formData = app.getFormDataForSchema();
        
        if (!formData || Object.keys(formData).length === 0) {
            console.warn('📝 Form Data Logging - No data available');
            const emptyData = {
                "_note": "No form data available",
                "_suggestion": "Please fill out the form fields and try again",
                "_schema": app.currentSchema || "No schema selected",
                "_timestamp": new Date().toISOString()
            };
            console.log(emptyData);
            return emptyData;
        }
        
        // Transform the form data to handle indexed container fields (schema-driven)
        const schemaInfo = this.getSchemaInfo(app);
        console.log('SchemaInfo from getSchemaInfo:', schemaInfo);
        
        const transformedData = JSONResponseBuilder.transformFormDataForStores(formData, schemaInfo);
        
        // Get full schema object for dynamic field extraction
        let fullSchemaObject = null;
        if (window.dynamicWorkflow && window.dynamicWorkflow.currentSchemaData) {
            fullSchemaObject = {
                workflow_name: app.currentSchema,
                schemas: {
                    RootModel: window.dynamicWorkflow.currentSchemaData
                }
            };
        }
        
        // If we don't have a full schema object, but we have schemaInfo with containerName,
        // create a minimal schema object that our extraction function can understand
        if (!fullSchemaObject && schemaInfo && schemaInfo.containerName) {
            fullSchemaObject = {
                workflow_name: app.currentSchema,
                schemas: {
                    RootModel: {
                        properties: {
                            [schemaInfo.containerName]: {
                                type: 'array',
                                items: {}
                            }
                        }
                    }
                }
            };
            console.log('Created minimal schema object from schemaInfo:', fullSchemaObject);
        }
        
        const formattedData = JSONResponseBuilder.createFormattedJsonStructure(
            transformedData, 
            app.selectedPromptVersion, 
            app.currentSchema, 
            fullSchemaObject || schemaInfo.schema
        );

    // Return the full structure with user_prompt and conversation_flow
    console.log('=== FORM DATA JSON (full) ===');
    console.log('Raw form data:', formData);
    console.log('Transformed data:', transformedData);
    console.log('Formatted JSON structure:', formattedData);
    console.log('JSON formatted:', JSON.stringify(formattedData, null, 2));
    console.log('=== END FORM DATA ===');
    return formattedData;
    }

    /**
     * Force data synchronization with DOM
     */
    static forceDataSync(app) {
        try {
            if (window.dynamicWorkflow && typeof window.dynamicWorkflow.collectFormDataFromDOM === 'function') {
                const domData = window.dynamicWorkflow.collectFormDataFromDOM();
                
                if (domData && Object.keys(domData).length > 0 && window.dynamicWorkflow.dataManager) {
                    const storedData = window.dynamicWorkflow.dataManager.getFormDataForSchema(app.currentSchema) || {};
                    const mergedData = { ...storedData, ...domData };
                    
                    if (typeof window.dynamicWorkflow.dataManager.setFormData === 'function') {
                        window.dynamicWorkflow.dataManager.setFormData(app.currentSchema, mergedData);
                        console.log('Force synced data from DOM:', mergedData);
                    }
                }
            }
        } catch (error) {
            console.error('Error in forceDataSync:', error);
        }
    }

    /**
     * Get form data (enhanced to prioritize fresh DOM data)
     */
    static getFormDataForSchema(app) {
        try {
            let formData = {};
            
            // Method 1: Get data from dynamic workflow system
            if (window.dynamicWorkflow && 
                typeof window.dynamicWorkflow.getFormDataForSchema === 'function') {
                formData = window.dynamicWorkflow.getFormDataForSchema() || {};
            }
            
            // Method 2: Always collect fresh data from DOM and merge
            const freshDomData = app.collectFormDataDirectly();
            if (freshDomData && Object.keys(freshDomData).length > 0) {
                formData = { ...formData, ...freshDomData };
                console.log('Merged stored and fresh DOM data:', formData);
            }
            
            // Method 3: Fallback if no data found
            if (Object.keys(formData).length === 0) {
                console.log('No data found, using comprehensive DOM scan');
                formData = app.collectFormDataDirectly();
            }
            
            return formData;
        } catch (error) {
            console.error('Error getting form data:', error);
            return app.collectFormDataDirectly();
        }
    }

    /**
     * Enhanced fallback method to collect form data directly from DOM
     */
    static collectFormDataDirectly(app) {
        const formData = {};
        
        try {
            const container = document.getElementById('dynamicFormsContainer');
            if (!container) {
                console.log('Dynamic forms container not found');
                return formData;
            }
            
            // Collect data from all input types
            const inputs = container.querySelectorAll('input, select, textarea');
            inputs.forEach(input => {
                if (input.id) {
                    let fieldName = FormDataUtils.parseFieldNameFromInputId(input.id);
                    let value = input.value;
                    
                    if (value.trim() === '' && input.type !== 'checkbox' && input.type !== 'radio') {
                        return;
                    }
                    
                    if (input.type === 'number' && value !== '') {
                        value = parseFloat(value) || 0;
                    } else if (input.type === 'checkbox') {
                        value = input.checked;
                    } else {
                        value = value.trim();
                    }
                    
                    FormDataUtils.setNestedFieldValue(formData, fieldName, value);
                }
            });
            
            // Collect data from selected union options
            const selectedOptions = container.querySelectorAll('.option-card.selected');
            selectedOptions.forEach(option => {
                const optionName = option.querySelector('.option-name');
                const parentGroup = option.closest('.form-group');
                if (optionName && parentGroup) {
                    const label = parentGroup.querySelector('.form-label');
                    if (label) {
                        const fieldName = FormDataUtils.sanitizeFieldName(label.textContent);
                        formData[fieldName] = optionName.textContent.trim();
                    }
                }
            });
            
            // Collect data from array containers
            const arrayContainers = container.querySelectorAll('.array-container, [class*="array"]');
            arrayContainers.forEach(arrayContainer => {
                const arrayFieldName = FormDataUtils.extractArrayFieldName(arrayContainer);
                if (arrayFieldName) {
                    const arrayData = FormDataUtils.collectArrayData(arrayContainer);
                    if (arrayData.length > 0) {
                        formData[arrayFieldName] = arrayData;
                    }
                }
            });
            
            console.log('Enhanced direct form data collection result:', formData);
            
        } catch (error) {
            console.error('Error in enhanced direct form data collection:', error);
        }
        
        return formData;
    }

    /**
     * Initialize form data tracking
     */
    static initFormDataTracking(app) {
        setInterval(() => {
            this.updateFormDataStatus(app);
        }, 500);
        
        this.updateFormDataStatus(app);
    }

    /**
     * Update form data status
     */
    static updateFormDataStatus(app) {
        try {
            const container = document.getElementById('dynamicFormsContainer');
            if (!container) {
                app.formDataExists = false;
                return;
            }
            
            let hasData = false;
            
            const inputs = container.querySelectorAll('input, select, textarea');
            for (let input of inputs) {
                if (input.type === 'checkbox' || input.type === 'radio') {
                    if (input.checked) {
                        hasData = true;
                        break;
                    }
                } else if (input.value && input.value.trim() !== '') {
                    hasData = true;
                    break;
                }
            }
            
            if (!hasData) {
                const selectedOptions = container.querySelectorAll('.option-card.selected');
                hasData = selectedOptions.length > 0;
            }
            
            app.formDataExists = hasData;
            
        } catch (error) {
            console.error('Error in updateFormDataStatus:', error);
            app.formDataExists = false;
        }
    }

    /**
     * Download form data as JSON file
     */
    static downloadFormDataJson(app) {
        app.forceDataSync();
        
        const formData = app.getFormDataForSchema();
        
        if (!formData || Object.keys(formData).length === 0) {
            alert('No form data available to download. Please fill out the form fields first.');
            return;
        }
    // Reuse constructRawJson and extract the inner user_prompt payload
    const downloadData = this.constructRawJson(app);
    const jsonString = JSON.stringify(downloadData, null, 2);
        
        const blob = new Blob([jsonString], { type: 'application/json' });
        const url = URL.createObjectURL(blob);
        const link = document.createElement('a');
        link.href = url;
        
        const identifier = JSONResponseBuilder.generateCompactIdentifier();
        link.download = `${identifier}.json`;
        
        link.click();
        URL.revokeObjectURL(url);
        
    console.log('📥 Form data JSON downloaded (new format):', downloadData);
    }

    /**
     * Run evaluation with dynamic data
     */
    static async runEvaluationWithDynamicData(app) {
        app.isRunning = true;
        app.hasResults = false;
        
        try {
            // Ensure we have the freshest data
            app.forceDataSync();
            const dynamicFormData = app.getFormDataForSchema();
            if (!dynamicFormData || Object.keys(dynamicFormData).length === 0) {
                throw new Error('Please fill out the input form before running evaluation.');
            }

            // Build final JSON expected by backend
            const finalJson = app.constructFinalJson();

            // Resolve API URL for chat
            const base = window.API_CONFIG?.baseUrl || 'http://localhost:8000';
            const path = window.API_CONFIG?.endpoints?.chat || '/api/v1/chat';
            const url = `${base}${path}`;

            // POST to chat endpoint with timeout and better error handling
            let resp;
            try {
                // Add timeout to fetch request
                const controller = new AbortController();
                const timeoutId = setTimeout(() => controller.abort(), 60000); // 60 second timeout
                
                resp = await fetch(url, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(finalJson),
                    signal: controller.signal
                });
                
                clearTimeout(timeoutId);
            } catch (fetchError) {
                if (fetchError.name === 'AbortError') {
                    throw new Error('Request timeout - The evaluation took too long to complete. Try reducing the complexity of your input data.');
                } else if (fetchError.message.includes('NetworkError') || fetchError.message.includes('fetch')) {
                    throw new Error('Network connection error - Please check your internet connection and try again.');
                } else {
                    throw new Error(`Network error: ${fetchError.message}`);
                }
            }

            if (!resp.ok) {
                let errorText = 'Unknown error';
                try {
                    errorText = await resp.text();
                } catch (e) {
                    errorText = `HTTP ${resp.status} ${resp.statusText}`;
                }
                throw new Error(`Chat API error ${resp.status}: ${errorText}`);
            }

            // Capture raw response text first for robust parsing
            const rawText = await resp.clone().text();
            // Debug: Log raw response (truncated)
            try {
                const preview = rawText ? rawText.slice(0, 1000) : '';
                console.log('[ChatAPI] Raw response preview (<=1000 chars):', preview);
            } catch (_) {}
            let data;
            const contentType = resp.headers.get('content-type') || '';
            if (contentType.includes('application/json')) {
                data = await resp.json();
            } else {
                // Fallback: treat as text
                data = { message: rawText };
            }

            // Debug: Log parsed response summary
            try {
                console.log('[ChatAPI] Parsed response type:', typeof data);
                if (data && typeof data === 'object') {
                    console.log('[ChatAPI] Parsed response keys:', Object.keys(data));
                }
            } catch (_) {}

            // Normalize results for display
            const workflowOutput = typeof data === 'string' ? data : (data.message || data.output || JSON.stringify(data));
            const agentResults = Array.isArray(data.agentResults) ? data.agentResults : [];

            // Parse agent interactions using chat-response-parser.js if available
            let parsedAgentResponses = [];
            try {
                const parserFn = (typeof window !== 'undefined') ? window.parseAgentResponses : (typeof parseAgentResponses !== 'undefined' ? parseAgentResponses : null);
                if (typeof parserFn === 'function') {
                    // Prefer the exact raw response body first
                    console.log('[Parser] Calling parseAgentResponses with rawText length:', rawText ? rawText.length : 0);
                    let parsedJsonString = parserFn(rawText);
                    console.log('[Parser] Returned string length (rawText attempt):', parsedJsonString ? parsedJsonString.length : 0);
                    // If that returns empty, try structured fallbacks
                    if (parsedJsonString === '[]' || parsedJsonString === null || parsedJsonString === undefined) {
                        const rawForParser =
                            (typeof data.agent_response !== 'undefined' ? data.agent_response :
                            typeof data.agent_interactions !== 'undefined' ? data.agent_interactions :
                            typeof data.agentResults !== 'undefined' ? data.agentResults :
                            typeof data.message !== 'undefined' ? data.message :
                            typeof data.output !== 'undefined' ? data.output : data);
                        const parserInput = typeof rawForParser === 'string' ? rawForParser : JSON.stringify(rawForParser);
                        console.log('[Parser] Fallback call with parserInput type:', typeof rawForParser);
                        parsedJsonString = parserFn(parserInput);
                        console.log('[Parser] Returned string length (fallback attempt):', parsedJsonString ? parsedJsonString.length : 0);
                    }
                    try {
                        parsedAgentResponses = JSON.parse(parsedJsonString);
                        console.log('[Parser] Parsed responses count:', Array.isArray(parsedAgentResponses) ? parsedAgentResponses.length : 0);
                    } catch (e) {
                        console.warn('Failed to JSON.parse parsed agent responses string; using empty array.', e);
                        parsedAgentResponses = [];
                    }
                } else {
                    console.warn('parseAgentResponses is not available on window. Skipping agent parsing.');
                }
            } catch (e) {
                console.warn('Agent response parsing failed:', e);
            }

            app.results = { workflowOutput, agentResults, parsedAgentResponses };

            app.isRunning = false;
            app.hasResults = true;
            
            console.log('Evaluation completed successfully:', app.results);
            
            // Get workflow parameters for redirect
            const urlParams = new URLSearchParams(window.location.search);
            const workflowId = urlParams.get('workflow') || app.currentSchema || 'unknown';
            const revisionId = app.selectedPromptVersion || 'latest';
            
            // Store results in sessionStorage for the results page
            const storageKey = `evaluation_results_${workflowId}_${revisionId}`;
            try {
                sessionStorage.setItem(storageKey, JSON.stringify(app.results));
            } catch (storageError) {
                console.warn('Failed to store results in sessionStorage:', storageError);
            }
            
            // Small delay to ensure state is updated and storage is saved before redirect
            setTimeout(() => {
                window.location.href = `/results?id=${encodeURIComponent(workflowId)}&revision_id=${encodeURIComponent(revisionId)}`;
            }, 500);
            
        } catch (error) {
            console.error('Error running evaluation:', error);
            
            // Reset the running state and show error message
            app.isRunning = false;
            app.hasResults = false;
            
            // Show a simple alert with the error message
            alert(`Evaluation failed: ${error.message}`);
        }
    }

    /**
     * Generate enhanced evaluation results
     */
    static generateEnhancedResults(workflowId, inputData) {
        const workflowOutput = `Test`;
        
        const agentResults = [
        ];
        
        return { workflowOutput, agentResults };
    }

    /**
     * Load revisions from API
     */
    static async loadRevisionsFromAPI(app) {
        try {
            app.revisions = [
                {
                    id: 'test-v2',
                    name: 'test-v2',
                    date: new Date().toISOString().split('T')[0],
                    description: 'Enhanced modular architecture',
                    author: 'System',
                    status: 'latest'
                },
                {
                    id: 'test-v1',
                    name: 'test-v1',
                    date: '2024-03-10',
                    description: 'Production stable',
                    author: 'System',
                    status: 'stable'
                }
            ];
        } catch (error) {
            console.error('Error loading revisions:', error);
            app.revisions = [];
        }
    }

    /**
     * Download results
     */
    static downloadResults(app) {
        if (!app.results) return;
        
        const resultsData = {
            workflow: app.workflow.name,
            schema: app.currentSchema,
            timestamp: new Date().toISOString(),
            promptVersion: app.selectedPromptVersion,
            inputData: app.getFormDataForSchema(),
            workflowOutput: app.results.workflowOutput,
            agentResults: app.results.agentResults
        };
        
        const dataStr = JSON.stringify(resultsData, null, 2);
        const dataBlob = new Blob([dataStr], { type: 'application/json' });
        const url = URL.createObjectURL(dataBlob);
        const link = document.createElement('a');
        link.href = url;
        link.download = `${app.workflow.name.replace(/\s+/g, '_')}_evaluation_${new Date().toISOString().split('T')[0]}.json`;
        link.click();
        URL.revokeObjectURL(url);
    }

    /**
     * Toggle JSON Preview functionality
     */
    static toggleJsonPreview(app) {
        app.showJsonPreview = !app.showJsonPreview;
        
        if (app.showJsonPreview) {
            // Initialize with Raw JSON by default
            app.jsonViewType = 'raw';
            this.updateJsonPreview(app);
        } else {
            // Clear data when hiding
            app.currentJsonData = null;
        }
    }

    /**
     * Update JSON Preview content based on selected view type
     */
    static updateJsonPreview(app) {
        try {
            // Force data synchronization before generating JSON
            app.forceDataSync();
            
            const formData = app.getFormDataForSchema();
            
            if (!formData || Object.keys(formData).length === 0) {
                app.currentJsonData = {
                    "_note": "No form data available",
                    "_suggestion": "Please fill out the form fields and try again",
                    "_schema": app.currentSchema || "No schema selected",
                    "_timestamp": new Date().toISOString()
                };
                return;
            }

            if (app.jsonViewType === 'raw') {
                // Generate Raw JSON (full formatted structure)
                app.currentJsonData = this.constructRawJson(app);
            } else if (app.jsonViewType === 'final') {
                // Generate Final JSON (same as constructFinalJson)
                const formattedData = this.constructRawJson(app);
                
                app.currentJsonData = {
                    user_prompt: JSON.stringify(formattedData.user_prompt),
                    conversation_flow: formattedData.conversation_flow
                };
            }
        } catch (error) {
            console.error('Error updating JSON preview:', error);
            app.currentJsonData = {
                "_error": "Failed to generate JSON preview",
                "_details": error.message,
                "_timestamp": new Date().toISOString()
            };
        }
    }

    /**
     * Format JSON data for HTML display with syntax highlighting
     */
    static formatJsonForDisplay(jsonData) {
        if (!jsonData) {
            return '<span class="text-muted">No data to display</span>';
        }
        
        try {
            const jsonString = JSON.stringify(jsonData, null, 2);
            
            // Simple syntax highlighting
            const highlighted = jsonString
                .replace(/("(?:\\.|[^"\\])*")(\s*:\s*)/g, '<span class="json-key">$1</span>$2')
                .replace(/:\s*("(?:\\.|[^"\\])*")/g, ': <span class="json-string">$1</span>')
                .replace(/:\s*(\d+(?:\.\d+)?)/g, ': <span class="json-number">$1</span>')
                .replace(/:\s*(true|false)/g, ': <span class="json-boolean">$1</span>')
                .replace(/:\s*(null)/g, ': <span class="json-null">$1</span>');
            
            return highlighted;
        } catch (error) {
            console.error('Error formatting JSON for display:', error);
            return `<span class="text-danger">Error formatting JSON: ${error.message}</span>`;
        }
    }

    /**
     * Download currently displayed JSON
     */
    static downloadCurrentJson(app) {
        if (!app.currentJsonData) {
            alert('No JSON data available to download.');
            return;
        }
        
        try {
            const jsonString = JSON.stringify(app.currentJsonData, null, 2);
            const blob = new Blob([jsonString], { type: 'application/json' });
            const url = URL.createObjectURL(blob);
            const link = document.createElement('a');
            link.href = url;
            
            const identifier = JSONResponseBuilder.generateCompactIdentifier();
            const viewType = app.jsonViewType === 'final' ? 'final' : 'raw';
            link.download = `${identifier}_${viewType}_json.json`;
            
            link.click();
            URL.revokeObjectURL(url);
            
            console.log(`📥 ${viewType} JSON downloaded:`, app.currentJsonData);
        } catch (error) {
            console.error('Error downloading JSON:', error);
            alert(`Failed to download JSON: ${error.message}`);
        }
    }
}

// Export for global access
window.PromptEvaluationCore = PromptEvaluationCore;