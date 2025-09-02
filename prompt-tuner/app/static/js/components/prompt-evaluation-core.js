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
    static logFormDataToConsole(app) {
        app.forceDataSync();
        
        const formData = app.getFormDataForSchema();
        
        if (!formData || Object.keys(formData).length === 0) {
            console.warn('📝 Form Data Logging - No data available');
            console.log({
                "_note": "No form data available",
                "_suggestion": "Please fill out the form fields and try again",
                "_schema": app.currentSchema || "No schema selected",
                "_timestamp": new Date().toISOString()
            });
            return;
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
        
        console.log('=== FORM DATA JSON ===');
        console.log('Raw form data:', formData);
        console.log('Transformed data:', transformedData);
        console.log('Formatted JSON structure:', formattedData);
        console.log('JSON formatted:', JSON.stringify(formattedData, null, 2));
        console.log('=== END FORM DATA ===');
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
        
        const schemaInfo = this.getSchemaInfo(app);
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
        }
        
        const downloadData = JSONResponseBuilder.createFormattedJsonStructure(
            transformedData, 
            app.selectedPromptVersion, 
            app.currentSchema, 
            fullSchemaObject || schemaInfo.schema
        );
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
            const dynamicFormData = app.getFormDataForSchema();
            console.log('Running evaluation with modular data:', dynamicFormData);
            
            // Transform form data to match the required format
            const transformedFormData = {
                revision_id: app.selectedPromptVersion,
                identifier: app.evaluationId,
                ...dynamicFormData
            };
            
            // Prepare the API request payload in the required format
            const requestPayload = {
                user_prompt: JSON.stringify(transformedFormData),
                conversation_flow: app.currentSchema
            };
            
            // Simple request body log for testing
            console.log('REQUEST BODY:', JSON.stringify(requestPayload, null, 2));
            
            // Make API call to the chat endpoint
            const response = await fetch(`${window.API_CONFIG.baseUrl}${window.API_CONFIG.endpoints.chat}`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(requestPayload)
            });
            
            if (!response.ok) {
                const errorText = await response.text();
                console.error('Error Response Body:', errorText);
                throw new Error(`API request failed: ${response.status} ${response.statusText}`);
            }
            
            const apiResponse = await response.json();
            console.log('API response received:', apiResponse);
            
            // Process the API response and format for display
            app.results = PromptEvaluationCore.processApiResponse(apiResponse, app.currentSchema, dynamicFormData);
            
            app.isRunning = false;
            app.hasResults = true;
            
        } catch (error) {
            console.error('Error running evaluation:', error);
            app.isRunning = false;
            alert('Error running evaluation: ' + error.message);
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
     * Process API response and format for display
     */
    static processApiResponse(apiResponse, workflowName, inputData) {
        try {
            console.log('Processing API response:', apiResponse);
            
            // Extract the main workflow output
            let workflowOutput = 'No output received';
            
            // Check if we have agent_response data
            if (apiResponse.agent_response) {
                try {
                    // Parse the agent_response string to JSON
                    const agentResponseData = JSON.parse(apiResponse.agent_response);
                    console.log('Parsed agent response data:', agentResponseData);
                    
                    // Find the summary agent response for the main workflow output
                    const summaryAgent = agentResponseData.find(agent => 
                        agent.__dict__?.chat_name === 'summary'
                    );
                    
                    if (summaryAgent && summaryAgent.__dict__?.chat_response?.chat_message?.__dict__?.content) {
                        workflowOutput = summaryAgent.__dict__.chat_response.chat_message.__dict__.content;
                    } else {
                        // Fallback to first agent's response
                        const firstAgent = agentResponseData[0];
                        if (firstAgent && firstAgent.__dict__?.chat_response?.chat_message?.__dict__?.content) {
                            workflowOutput = firstAgent.__dict__.chat_response.chat_message.__dict__.content;
                        }
                    }
                } catch (parseError) {
                    console.error('Error parsing agent_response:', parseError);
                    workflowOutput = 'Error parsing agent response data';
                }
            }
            
            // Process agent results if available
            const agentResults = [];
            
            if (apiResponse.agent_response) {
                try {
                    const agentResponseData = JSON.parse(apiResponse.agent_response);
                    
                    agentResponseData.forEach((agent, index) => {
                        const agentDict = agent.__dict__;
                        if (!agentDict) return;
                        
                        const chatResponse = agentDict.chat_response?.chat_message?.__dict__;
                        const agentName = agentDict.chat_name || `agent_${index + 1}`;
                        
                        // Clean up agent display name
                        const displayName = BaseManager.cleanDisplayName(agentName);
                        
                        agentResults.push({
                            agentName: agentName,
                            displayName: displayName,
                            output: chatResponse?.content || 'No output available',
                            tokensUsed: (agentDict.prompt_tokens || 0) + (agentDict.completion_tokens || 0),
                            model: chatResponse?.models_usage?.model || 'Unknown',
                            executionTime: agentDict.end_time && agentDict.start_time ? 
                                Math.round((agentDict.end_time - agentDict.start_time) * 1000) : 0,
                            expanded: false, // For UI state
                            promptTokens: agentDict.prompt_tokens || 0,
                            completionTokens: agentDict.completion_tokens || 0
                        });
                    });
                } catch (parseError) {
                    console.error('Error processing individual agents:', parseError);
                }
            }
            
            // If no agent results, create a default entry from the main response
            if (agentResults.length === 0) {
                agentResults.push({
                    agentName: 'workflow_agent',
                    displayName: 'Workflow Agent',
                    output: workflowOutput,
                    tokensUsed: apiResponse.token_count || 0,
                    model: 'Unknown',
                    executionTime: 0,
                    expanded: false,
                    promptTokens: 0,
                    completionTokens: apiResponse.token_count || 0
                });
            }
            
            return {
                workflowOutput,
                agentResults,
                evaluationId: apiResponse.message_id || null,
                threadId: apiResponse.thread_id || null,
                totalTokens: apiResponse.token_count || 0,
                timestamp: new Date().toISOString()
            };
            
        } catch (error) {
            console.error('Error processing API response:', error);
            return {
                workflowOutput: 'Error processing response: ' + error.message,
                agentResults: [],
                evaluationId: null,
                threadId: null,
                totalTokens: 0,
                timestamp: new Date().toISOString()
            };
        }
    }

    /**
     * Load revisions from API
     */
    static async loadRevisionsFromAPI(app) {
        try {
            console.log('Loading revisions from API for workflow:', app.workflowQueryParam);
            
            // Fetch workflows list from the API
            const response = await fetch(`${API_CONFIG.baseUrl}${API_CONFIG.endpoints.workflowsList}`);
            
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            
            const data = await response.json();
            console.log('Workflows API Response:', data);
            
            if (app.workflowQueryParam) {
                // Find the specific workflow
                const workflow = data.workflows.find(w => w.workflow === app.workflowQueryParam);
                
                if (workflow && workflow.prompt_files && workflow.prompt_files.length > 0) {
                    // Create revisions data based on the workflow's revision_id (only if prompt files exist)
                    app.revisions = [{
                        id: workflow.revision_id,
                        name: workflow.revision_id,
                        date: new Date().toISOString().split('T')[0],
                        description: `Revision ${workflow.revision_id}`,
                        author: 'System',
                        status: 'active'
                    }];
                    
                    console.log('Successfully loaded revisions:', app.revisions);
                } else {
                    console.log('Workflow not found or no prompt files available:', app.workflowQueryParam);
                    app.revisions = [];
                }
            } else {
                // If no specific workflow, collect all unique revisions from workflows that have prompt files
                const uniqueRevisions = new Map();
                
                data.workflows.forEach(workflow => {
                    if (workflow.revision_id && workflow.prompt_files && workflow.prompt_files.length > 0 && !uniqueRevisions.has(workflow.revision_id)) {
                        uniqueRevisions.set(workflow.revision_id, {
                            id: workflow.revision_id,
                            name: workflow.revision_id,
                            date: new Date().toISOString().split('T')[0],
                            description: `Revision ${workflow.revision_id}`,
                            author: 'System',
                            status: 'active'
                        });
                    }
                });
                
                app.revisions = Array.from(uniqueRevisions.values());
                console.log('Successfully loaded all available revisions with prompt files:', app.revisions);
            }
        } catch (error) {
            console.error('Error loading revisions from API:', error);
            // Fallback to empty array instead of hardcoded data
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
            evaluationId: app.evaluationId,
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
        
        // Create filename with prompt version and evaluation ID
        const workflowName = app.workflow.name.replace(/\s+/g, '_');
        const promptVersion = app.selectedPromptVersion || 'unknown';
        const evaluationId = app.evaluationId || 'no-id';
        const dateStr = new Date().toISOString().split('T')[0];
        
        link.download = `${workflowName}_v${promptVersion}_eval${evaluationId}_${dateStr}.json`;
        link.click();
        URL.revokeObjectURL(url);
    }
}

// Export for global access
window.PromptEvaluationCore = PromptEvaluationCore;