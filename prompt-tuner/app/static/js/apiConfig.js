const API_CONFIG = {
    baseUrl: 'http://localhost:8000',
    endpoints: {
        workflows: '/api/v1/workflows',
        workflowAgents: '/api/v1/custom-workflows/agents/{workflow-name}'
        // Add more endpoints as needed
    }
};
window.API_CONFIG = API_CONFIG; // Make it globally available