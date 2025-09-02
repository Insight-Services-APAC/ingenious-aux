const API_CONFIG = {
    baseUrl: 'http://localhost:8000',
    endpoints: {
        workflows: '/api/v1/workflows',
        workflowAgents: '/api/v1/custom-workflows/agents/{workflow-name}',
        workflowsList: '/api/v1/workflows/list',
        promptView: '/api/v1/prompts/view', 
        promptUpdate: '/api/v1/prompts/update',
        workflowSchemaRetriever: '/api/v1/custom-workflows/schema/{custom-workflow-name}',
        chat: '/api/v1/chat'
        // Add more endpoints as needed
    }
};
window.API_CONFIG = API_CONFIG; // Make it globally availables