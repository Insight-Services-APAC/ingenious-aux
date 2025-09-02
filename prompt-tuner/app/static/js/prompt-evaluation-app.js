/**
 * Prompt Evaluation App - Main Application Logic
 * Alpine.js application with UI interaction methods and state management
 */

/**
 * Enhanced Prompt Evaluation App using Modular Dynamic Workflow Architecture
 * This is the main Alpine.js app function with complex logic delegated to external modules
 */
function promptEvaluationApp() {
    return {
        // State from DynamicWorkflowManager
        currentSchema: null,
        availableWorkflows: [],
        schemasLoaded: false,
        showFormHeader: false,
        showFormActions: false,
        showResults: false,
        formTitle: 'Dynamic Form',
        dynamicFormHtml: '',
        resultsHtml: '',
        
        // Evaluation-specific state
        workflow: { name: 'Workflow Evaluation', id: null },
        isRunning: false,
        hasResults: false,
        results: null,
        selectedPromptVersion: '',
        revisions: [],
        workflowQueryParam: null,
        formDataExists: false,
        
        // JSON Preview state
        showJsonPreview: false,
        jsonViewType: 'raw',
        currentJsonData: null,
        
        // Initialization
        async init() {
            this.generateNewEvaluationId(); // Initialize with a new evaluation ID
            return await PromptEvaluationCore.initialize(this);
        },
        
        // Schema selection (delegate to DynamicWorkflowManager)
        async selectSchema(schemaName) {
            if (window.dynamicWorkflow) {
                await window.dynamicWorkflow.selectSchema(schemaName);
                this.syncState();
            }
        },
        
        // Simple utility functions that stay inline
        generateCompactIdentifier() {
            return JSONResponseBuilder.generateCompactIdentifier();
        },

        generateNewEvaluationId() {
            // Generate 6 digit random number
            const randomNumber = Math.floor(Math.random() * 1000000).toString().padStart(6, '0');
            this.evaluationId = randomNumber;
            return this.evaluationId;
        },

        createFormattedJsonStructure(formData) {
            // DEBUG: Log schema construction details
            if (window.dynamicWorkflow?.currentSchemaData) {
                console.log('currentSchemaData structure:', JSON.stringify(window.dynamicWorkflow.currentSchemaData, null, 2));
            }
            
            // Get the full schema object for dynamic field extraction
            const schemaInfo = PromptEvaluationCore.getSchemaInfo(this);
            console.log('schemaInfo from PromptEvaluationCore:', schemaInfo);
            const schemaObject = schemaInfo ? schemaInfo.schema : null;
            
            // Try to get full schema from dynamicWorkflow if available
            let fullSchemaObject = null;
            if (window.dynamicWorkflow && window.dynamicWorkflow.currentSchemaData) {
                fullSchemaObject = {
                    workflow_name: this.currentSchema,
                    schemas: {
                        RootModel: window.dynamicWorkflow.currentSchemaData
                    }
                };
                console.log('Constructed fullSchemaObject:', JSON.stringify(fullSchemaObject, null, 2));
            } else {
                console.log('No currentSchemaData available, using schemaObject:', schemaObject);
            }
            
            return JSONResponseBuilder.createFormattedJsonStructure(
                formData, 
                this.selectedPromptVersion, 
                this.currentSchema, 
                fullSchemaObject || schemaObject
            );
        },

        constructRawJson() {
            return PromptEvaluationCore.constructRawJson(this);
        },

        // Build and log the final JSON payload in the required format
        constructFinalJson() {
            try {
                // Use the core function to get formatted data and log it
                const formattedData = PromptEvaluationCore.constructRawJson(this);


                // Use the inner payload for user_prompt, and conversation_flow from formattedData
                const finalJson = {
                    user_prompt: JSON.stringify(formattedData.user_prompt),
                    conversation_flow: formattedData.conversation_flow
                };

                return finalJson;
            } catch (err) {
                console.error('Failed to build final JSON:', err);
            }
        },
        
        // Complex functions delegated to external modules
        async waitForDynamicWorkflow() {
            return await PromptEvaluationCore.waitForDynamicWorkflow();
        },
        
        setupStateSync() {
            return PromptEvaluationCore.setupStateSync(this);
        },
        
        syncState() {
            return PromptEvaluationCore.syncState(this);
        },
        
        forceDataSync() {
            return PromptEvaluationCore.forceDataSync(this);
        },
        
        getFormDataForSchema() {
            return PromptEvaluationCore.getFormDataForSchema(this);
        },
        
        collectFormDataDirectly() {
            return PromptEvaluationCore.collectFormDataDirectly(this);
        },
        
        initFormDataTracking() {
            return PromptEvaluationCore.initFormDataTracking(this);
        },
        
        updateFormDataStatus() {
            return PromptEvaluationCore.updateFormDataStatus(this);
        },
        
        downloadFormDataJson() {
            return PromptEvaluationCore.downloadFormDataJson(this);
        },
        
        async runEvaluationWithDynamicData() {
            return await PromptEvaluationCore.runEvaluationWithDynamicData(this);
        },
        
        generateEnhancedResults(workflowId, inputData) {
            return PromptEvaluationCore.generateEnhancedResults(workflowId, inputData);
        },
        
        async loadRevisionsFromAPI() {
            return await PromptEvaluationCore.loadRevisionsFromAPI(this);
        },
        
        downloadResults() {
            return PromptEvaluationCore.downloadResults(this);
        },
        
        // Simple functions kept inline for Alpine.js
        initializePromptVersion() {
            const versions = this.getAvailableVersions();
            if (versions.length > 0) {
                this.selectedPromptVersion = versions[0].id;
            }
        },
        
        getAvailableVersions() {
            return this.revisions.map(revision => ({
                id: revision.id,
                display: `${revision.name} (${revision.description})`,
                date: revision.date,
                status: revision.status
            }));
        },
        
        resetEvaluation() {
            this.isRunning = false;
            this.hasResults = false;
            this.results = null;
            if (window.dynamicWorkflow) {
                window.dynamicWorkflow.resetAll();
                this.syncState();
            }
        },
        
        formatWorkflowOutput(output) {
            return output.replace(/\n/g, '<br>').replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
        },
        
        getAgentDescription(agentName) {
            const descriptions = {
                'schema_validator': 'Validates schema structure and data integrity',
                'data_processor': 'Processes form data using modular architecture',
                'evaluation_engine': 'Evaluates workflow performance and readiness'
            };
            return descriptions[agentName] || 'Specialized evaluation agent';
        },
        
        async copyAgentOutput(output) {
            try {
                await navigator.clipboard.writeText(output);
                console.log('Agent output copied to clipboard');
            } catch (err) {
                console.error('Failed to copy to clipboard:', err);
            }
        },
        
        // Helper methods that can stay inline
        hasFormData() {
            const formData = this.getFormDataForSchema();
            return formData && Object.keys(formData).length > 0;
        },
        
        hasAnyFormData() {
            return this.formDataExists;
        },

        // Format agent names like "fiscal_analysis_agent" -> "Fiscal Analysis Agent"
        formatAgentName(rawName) {
            try {
                if (!rawName || typeof rawName !== 'string') return 'Agent';
                // Normalize separators to spaces
                let s = rawName.replace(/[_-]+/g, ' ').replace(/\s+/g, ' ').trim();
                if (!s) return 'Agent';

                const ACRONYMS = new Set(['ai', 'nps', 'nsw', 'usa', 'uk', 'eu', 'id']);

                const words = s.split(' ');
                const titled = words.map(w => {
                    const lower = w.toLowerCase();
                    if (ACRONYMS.has(lower)) return lower.toUpperCase();
                    // Preserve already-cased words reasonably
                    return lower.charAt(0).toUpperCase() + lower.slice(1);
                });
                return titled.join(' ');
            } catch (_) {
                return rawName || 'Agent';
            }
        },
        
        // JSON Preview functionality
        toggleJsonPreview() {
            return PromptEvaluationCore.toggleJsonPreview(this);
        },
        
        updateJsonPreview() {
            return PromptEvaluationCore.updateJsonPreview(this);
        },
        
        formatJsonForDisplay(jsonData) {
            return PromptEvaluationCore.formatJsonForDisplay(jsonData);
        },
        
        downloadCurrentJson() {
            return PromptEvaluationCore.downloadCurrentJson(this);
        }
    };
}

// Export for global access
window.promptEvaluationApp = promptEvaluationApp;