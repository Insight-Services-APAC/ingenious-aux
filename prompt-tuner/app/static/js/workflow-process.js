// Workflow Process JavaScript with Alpine.js

// Access API configuration
const { baseUrl, endpoints } = window.API_CONFIG;

// Alpine.js data for workflow process page
function workflowProcessApp() {
    return {
        workflow: {
            id: '',
            name: 'Loading...',
            description: 'Loading workflow details...',
            status: 'loading',
            agents: []
        },
        currentStep: -1, // Start with no active step
        loading: false,
        error: null,
        
        // Initialize the application
        async init() {
            const workflowId = this.getWorkflowIdFromUrl();
            if (workflowId) {
                await this.loadWorkflowDetails(workflowId);
            } else {
                this.error = 'No workflow ID specified';
                console.error('No workflow ID found in URL');
            }
        },
        
        // Get workflow ID from URL parameters
        getWorkflowIdFromUrl() {
            const urlParams = new URLSearchParams(window.location.search);
            return urlParams.get('id') || urlParams.get('workflow');
        },
        
        // Load workflow details
        async loadWorkflowDetails(workflowId) {
            this.loading = true;
            
            try {
                // First, get the workflow name and description from the workflows API
                const workflowInfo = await this.getWorkflowInfo(workflowId);
                
                if (workflowInfo) {
                    this.workflow.name = workflowInfo.workflow.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase());
                    this.workflow.description = workflowInfo.description;
                    this.workflow.status = workflowInfo.ready ? 'ready' : 'development';
                }
                
                // Then load workflow agents from the agents API endpoint
                await this.loadWorkflowAgents(workflowId);
                
            } catch (error) {
                console.error('Error loading workflow details:', error);
                this.error = error.message;
            } finally {
                this.loading = false;
            }
        },
        
        // Get workflow info from the workflows API (same as used in workflow hub)
        async getWorkflowInfo(workflowId) {
            try {
                const response = await fetch(`${API_CONFIG.baseUrl}${API_CONFIG.endpoints.workflows}`);
                
                if (!response.ok) {
                    throw new Error(`HTTP error! status: ${response.status}`);
                }
                
                const data = await response.json();
                
                // Find the workflow by ID, supporting both formats (bike_insights and bike-insights)
                const workflow = data.workflows.find(w => 
                    w.workflow === workflowId || 
                    w.supported_names?.includes(workflowId) ||
                    w.workflow.replace(/-/g, '_') === workflowId ||
                    w.workflow.replace(/_/g, '-') === workflowId
                );
                
                if (workflow) {
                    console.log('Found workflow info from API:', workflow);
                    return workflow;
                } else {
                    throw new Error(`Workflow '${workflowId}' not found in workflows API`);
                }
                
            } catch (error) {
                console.error('Error fetching workflow info from API:', error);
            }
        },
        
        // Load workflow agents from API
        async loadWorkflowAgents(workflowName) {
            try {
                const apiUrl = `${API_CONFIG.baseUrl}${API_CONFIG.endpoints.workflowAgents.replace('{workflow-name}', workflowName)}`;
                console.log('Attempting to fetch agents from:', apiUrl);
                
                const response = await fetch(apiUrl);
                
                if (!response.ok) {
                    throw new Error(`HTTP error! status: ${response.status}`);
                }
                
                const data = await response.json();
                
                // Update workflow with agents data only (preserve name/description from workflows API)
                this.workflow.id = data.workflow_name;
                this.workflow.agents = data.agents || []; // Ensure agents is always an array
                
                console.log('Loaded workflow agents from API:', data);
                
                // Log if no agents were found
                if (!data.agents || data.agents.length === 0) {
                    console.warn('No agents found for workflow:', workflowName);
                }
                
            } catch (error) {
                console.error('Error loading workflow agents from API:', error);
                // No fallback data - just set empty agents array to show "not found" message
                this.workflow.agents = [];
                console.warn('No agents data available for workflow:', workflowName);
            }
        },
        
        // Get status badge class
        getStatusBadgeClass(status) {
            const statusClasses = {
                'ready': 'bg-success',
                'development': 'bg-warning',
                'maintenance': 'bg-secondary',
                'error': 'bg-danger',
                'running': 'bg-primary'
            };
            return statusClasses[status] || 'bg-secondary';
        },
        
        // Format status text
        formatStatus(status) {
            return status.charAt(0).toUpperCase() + status.slice(1);
        },
        
        // Run evaluation
        async runEvaluation() {
            if (!this.workflow.id || this.workflow.agents.length === 0) return;
            
            // Redirect to prompt evaluation page with workflow parameter
            window.location.href = `prompt-evaluation.html?workflow=${this.workflow.id}`;
        },
        
        // Simulate workflow execution with progress
        async simulateWorkflowExecution() {
            const steps = this.workflow.agents.length;
            
            for (let i = 0; i < steps; i++) {
                this.currentStep = i;
                await new Promise(resolve => setTimeout(resolve, 1000)); // Wait 1 second between steps
            }
            
            alert('Workflow execution completed successfully!');
            this.currentStep = -1; // Reset to no active step
        },
        
        // Manage prompts
        managePrompts() {
            if (!this.workflow.id || this.workflow.agents.length === 0) return;
            
            console.log('Manage prompts for workflow:', this.workflow.id);
            
            // Redirect to manage prompts page with workflow information
            const params = new URLSearchParams({
                workflowId: this.workflow.id,
                workflowName: this.workflow.name
            });
            
            window.location.href = `manage-prompts.html?${params.toString()}`;
        }
    };
}

// Export for use in HTML
window.workflowProcessApp = workflowProcessApp;
