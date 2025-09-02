
// Access API configuration
const { baseUrl, endpoints } = window.API_CONFIG;

function managePromptsApp() {
    return {
        // Data properties
        workflowId: null,
        workflowName: 'Selected Workflow',
        selectedRevision: 'all',
        prompts: [],
        revisions: [],
        filteredPrompts: [],
        selectedPrompt: null, // For the view modal
        editPromptData: {}, // For the edit modal
        isCreatingNewPrompt: false, // Track if we're creating or editing
        lastSavedTime: null,
        loading: false,
        error: null,

        // Initialize the application
        async init() {
            this.loadWorkflowInfo();
            await this.loadWorkflowData();
            this.filterPrompts();
        },

        // Load workflow information from URL parameters or storage
        loadWorkflowInfo() {
            const urlParams = new URLSearchParams(window.location.search);
            this.workflowId = urlParams.get('id') || urlParams.get('workflowId');
            this.workflowName = this.formatWorkflowName(this.workflowId);
        },

        // Format workflow name for display
        formatWorkflowName(workflowId) {
            return workflowId
                .split('_')
                .map(word => word.charAt(0).toUpperCase() + word.slice(1))
                .join(' ');
        },

    // ...existing code...

        // Load workflow data from APIs
        async loadWorkflowData() {
            try {
                this.loading = true;
                console.log('Loading workflow data for:', this.workflowId);
                
                // Fetch workflows list from the API
                const response = await fetch(`${API_CONFIG.baseUrl}${API_CONFIG.endpoints.workflowsList}`);
                
                if (!response.ok) {
                    throw new Error(`HTTP error! status: ${response.status}`);
                }
                
                const data = await response.json();
                console.log('Workflows API Response:', data);
                
                // Find the specific workflow
                const workflow = data.workflows.find(w => w.workflow === this.workflowId);
                
                if (workflow && workflow.prompt_files && workflow.prompt_files.length > 0) {
                    // Create revisions data (using revision_id)
                    this.revisions = [{
                        id: workflow.revision_id,
                        name: `${workflow.revision_id}`,
                        date: new Date().toISOString().split('T')[0],
                        description: `Revision ${workflow.revision_id}`,
                        author: 'System',
                        status: 'active'
                    }];
                    
                    // Load prompts for each file
                    this.prompts = [];
                    
                    for (const filename of workflow.prompt_files) {
                        try {
                            console.log(`Loading prompt content for: ${filename}`);
                            const promptContent = await this.loadPromptContent(workflow.revision_id, filename);
                            
                            this.prompts.push({
                                id: `prompt-${filename.replace(/\.[^/.]+$/, "")}`,
                                name: this.formatPromptName(filename),
                                revision_id: workflow.revision_id,
                                status: 'active',
                                last_modified: new Date().toISOString().split('T')[0],
                                author: 'System',
                                size: promptContent.length,
                                preview: this.generatePreview(promptContent),
                                file_path: filename,
                                type: 'system',
                                content: promptContent
                            });
                        } catch (error) {
                            console.error(`Error loading prompt ${filename}:`, error);
                            // Add placeholder for failed prompt
                            this.prompts.push({
                                id: `prompt-${filename.replace(/\.[^/.]+$/, "")}`,
                                name: this.formatPromptName(filename),
                                revision_id: workflow.revision_id,
                                status: 'error',
                                last_modified: new Date().toISOString().split('T')[0],
                                author: 'System',
                                size: 0,
                                preview: 'Failed to load prompt content',
                                file_path: filename,
                                type: 'system',
                                content: 'Error loading content'
                            });
                        }
                    }
                    
                    console.log('Successfully loaded prompts:', this.prompts.length);
                } else {
                    console.log('No prompt files found for workflow:', this.workflowId);
                    // Don't use fallback data - just set empty arrays to show "not found" message
                    this.prompts = [];
                    this.revisions = [];
                }
                
            } catch (error) {
                console.error('Error loading workflow data:', error);
                // Don't use fallback data - just set empty arrays to show "not found" message
                this.prompts = [];
                this.revisions = [];
            } finally {
                this.loading = false;
            }
        },

        // Load prompt content from API
        async loadPromptContent(revisionId, filename) {
            const url = `${API_CONFIG.baseUrl}${API_CONFIG.endpoints.promptView}/${revisionId}/${filename}`;
            console.log('Fetching prompt content from:', url);
            
            const response = await fetch(url);
            
            if (!response.ok) {
                throw new Error(`Failed to load prompt content: ${response.status}`);
            }
            
            return await response.text();
        },

        // Format filename to readable prompt name
        formatPromptName(filename) {
            return filename
                .replace(/\.[^/.]+$/, "") // Remove extension
                .replace(/[_-]/g, ' ') // Replace underscores and dashes with spaces
                .replace(/\b(agent|prompt|prompts)\b/gi, '') // Remove "Agent", "Prompt", "Prompts" (case insensitive)
                .replace(/\s+/g, ' ') // Replace multiple spaces with single space
                .trim() // Remove leading/trailing spaces
                .replace(/\b\w/g, l => l.toUpperCase()); // Capitalize first letter of each word
        },

        // Generate preview from prompt content
        generatePreview(content) {
            const maxLength = 120;
            if (content.length <= maxLength) {
                return content;
            }
            return content.substring(0, maxLength) + '...';
        },

    // ...existing code...

        // Filter prompts based on selected revision
        filterPrompts() {
            if (this.selectedRevision === 'all') {
                this.filteredPrompts = [...this.prompts];
            } else {
                this.filteredPrompts = this.prompts.filter(prompt => prompt.revision_id === this.selectedRevision);
            }
        },

        // Get revision name by ID
        getRevisionName(revisionId) {
            const revision = this.revisions.find(r => r.id === revisionId);
            return revision ? revision.name : revisionId;
        },

        // Format version text to proper case
        formatVersionText(versionId) {
            if (!versionId) return '';
            // Convert v1, v2, etc. to V1, V2, etc.
            return versionId.charAt(0).toUpperCase() + versionId.slice(1).toLowerCase();
        },

        // Clean preview text by removing special characters and formatting
        cleanPreviewText(text) {
            if (!text) return '';
            
            return text
                // First remove any wrapper quotes
                .replace(/^["']|["']$/g, '')
                // Convert escaped backslashes first (to avoid interfering with other replacements)
                .replace(/\\\\/g, '\\')
                // Convert escaped newlines to actual spaces
                .replace(/\\n/g, ' ')
                // Convert escaped tabs to spaces
                .replace(/\\t/g, ' ')
                // Convert escaped quotes
                .replace(/\\"/g, '"')
                .replace(/\\'/g, "'")
                // Remove any remaining escape sequences
                .replace(/\\r/g, ' ')
                .replace(/\\f/g, ' ')
                .replace(/\\b/g, ' ')
                // Remove markdown headers (###, ##, #) but keep the text
                .replace(/#{1,6}\s*/g, '')
                // Remove markdown bold (**text**) but keep the text
                .replace(/\*\*(.*?)\*\*/g, '$1')
                // Remove markdown italic (*text*) but keep the text
                .replace(/\*(.*?)\*/g, '$1')
                // Clean up multiple spaces and normalize whitespace
                .replace(/\s+/g, ' ')
                // Remove common prefixes that don't add value to preview
                .replace(/^(System Prompt:|Prompt:|Instructions?:|You are|Role:?)\s*/i, '')
                .trim()
                // Limit length and add ellipsis
                .substring(0, 180) + '...';
        },

        // View prompt details
        viewPrompt(prompt) {
            console.log('Viewing prompt:', prompt.id);
            this.selectedPrompt = prompt;
            
            // Show the modal
            const modal = new bootstrap.Modal(document.getElementById('viewPromptModal'));
            modal.show();
        },

        // Get agent name from prompt (extract from file path)
        getAgentNameFromPrompt(prompt) {
            // Extract agent name from file path (remove .txt, .md extensions and convert to readable format)
            const fileName = prompt.file_path.split('/').pop().replace(/\.(txt|md)$/, '');
            return fileName.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase());
        },

        // Get full prompt content (returns actual API content with proper formatting)
        getPromptContent(prompt) {
            if (!prompt?.content) return 'No content available';
            
            // Process the content to handle escaped characters and formatting
            return prompt.content
                // Replace escaped newlines with actual newlines
                .replace(/\\n/g, '\n')
                // Replace escaped tabs with actual tabs
                .replace(/\\t/g, '\t')
                // Replace escaped quotes
                .replace(/\\"/g, '"')
                .replace(/\\'/g, "'")
                // Replace escaped backslashes
                .replace(/\\\\/g, '\\')
                // Remove any leading/trailing quotes if the whole content is wrapped
                .replace(/^["']|["']$/g, '')
                // Clean up any remaining escape sequences
                .replace(/\\r/g, '\r')
                .trim();
        },

        // Edit prompt
        editPrompt(prompt) {
            console.log('Editing prompt:', prompt);
            this.selectedPrompt = prompt;
            this.isCreatingNewPrompt = false; // Set flag for editing
            
            // Initialize edit data with current prompt data
            this.editPromptData = {
                id: prompt.id,
                name: prompt.name,
                fileName: prompt.file_path, // Use the actual file path from the prompt
                revision_id: prompt.revision_id,
                content: this.getPromptContent(prompt) // Use formatted content instead of raw content
            };
            
            console.log('Edit data initialized:', this.editPromptData);
            
            // Close view modal if open
            const viewModal = bootstrap.Modal.getInstance(document.getElementById('viewPromptModal'));
            if (viewModal) {
                viewModal.hide();
            }
            
            // Show edit modal
            const editModal = new bootstrap.Modal(document.getElementById('editPromptModal'));
            editModal.show();
        },

        // Computed property for content validation
        get isContentValid() {
            return this.editPromptData.content && 
                this.editPromptData.content.trim().length > 0 && 
                this.editPromptData.name && 
                this.editPromptData.name.trim().length > 0;
        },

        // Format prompt content
        formatPromptContent() {
            if (!this.editPromptData.content) return;
            
            // Basic formatting - ensure proper line breaks and remove excessive whitespace
            let formatted = this.editPromptData.content
                .replace(/\n\s*\n\s*\n/g, '\n\n') // Replace multiple empty lines with single
                .replace(/^\s+|\s+$/g, '') // Trim start and end
                .replace(/[ \t]+$/gm, ''); // Remove trailing spaces
            
            this.editPromptData.content = formatted;
        },

        // Insert template
        insertTemplate() {
            const template = `# ${this.editPromptData.name || 'Prompt Title'}

## Description
Describe what this prompt does and its purpose in the workflow.

## Instructions
You are an AI assistant specialized in [specific domain]. Your role is to:

1. [Specific instruction 1]
2. [Specific instruction 2]
3. [Specific instruction 3]

## Guidelines
- Always maintain a professional and helpful tone
- Provide accurate and relevant information
- Consider the user's context and requirements
- Follow the specific protocols for this agent type: ${this.editPromptData.type || 'system'}

## Example
User: [Sample user input]
Assistant: [Sample response demonstrating the expected behavior]

## Additional Notes
- File: ${this.editPromptData.fileName || 'prompt_name'}.jinja
- Version: ${this.getRevisionName(this.editPromptData.revision_id)}
- Type: ${this.editPromptData.type || 'system'}
`;

            if (this.editPromptData.content && this.editPromptData.content.trim()) {
                if (confirm('This will replace the current content. Are you sure?')) {
                    this.editPromptData.content = template;
                }
            } else {
                this.editPromptData.content = template;
            }
        },

        // Preview prompt
        previewPrompt() {
            if (!this.editPromptData.content) {
                alert('No content to preview');
                return;
            }
            
            // Create a temporary prompt object for preview
            const previewPrompt = {
                ...this.selectedPrompt,
                name: this.editPromptData.name,
                file_path: `/prompts/${this.editPromptData.fileName}.jinja`,
                revision_id: this.editPromptData.revision_id,
                type: this.editPromptData.type,
                size: this.editPromptData.content.length,
                preview: this.editPromptData.content.substring(0, 200)
            };
            
            // Update selectedPrompt temporarily for preview
            const originalPrompt = this.selectedPrompt;
            this.selectedPrompt = previewPrompt;
            
            // Close edit modal and show view modal
            const editModal = bootstrap.Modal.getInstance(document.getElementById('editPromptModal'));
            if (editModal) {
                editModal.hide();
            }
            
            setTimeout(() => {
                const viewModal = new bootstrap.Modal(document.getElementById('viewPromptModal'));
                viewModal.show();
                
                // Restore original prompt when preview modal is closed
                document.getElementById('viewPromptModal').addEventListener('hidden.bs.modal', () => {
                    this.selectedPrompt = originalPrompt;
                }, { once: true });
            }, 300);
        },

        // Save prompt changes
        async savePromptChanges() {
            if (!this.isContentValid) {
                alert('Please fill in all required fields');
                return;
            }
            
            try {
                console.log('Saving prompt changes:', this.editPromptData);
                
                // Check if this is a new prompt or existing prompt
                const existingPromptIndex = this.prompts.findIndex(p => p.id === this.editPromptData.id);
                const isNewPrompt = existingPromptIndex === -1;
                
                // Ensure filename has .jinja extension
                let filename = this.editPromptData.fileName;
                if (!filename.endsWith('.jinja')) {
                    filename = `${filename}.jinja`;
                }
                
                const revisionId = this.editPromptData.revision_id;
                
                // Construct the API URL: /api/v1/prompts/update/{revision_id}/{filename}
                const url = `${API_CONFIG.baseUrl}${API_CONFIG.endpoints.promptUpdate}/${revisionId}/${filename}`;
                
                console.log('API URL:', url);
                console.log('Revision ID:', revisionId);
                console.log('Filename:', filename);
                console.log('Is new prompt:', isNewPrompt);
                
                const requestBody = {
                    content: this.editPromptData.content,
                    name: this.editPromptData.name
                };
                
                console.log('Request body:', requestBody);
                
                const response = await fetch(url, {
                    method: 'POST',
                    headers: { 
                        'Content-Type': 'application/json',
                        'Accept': 'application/json'
                    },
                    body: JSON.stringify(requestBody)
                });
                
                console.log('Response status:', response.status);
                
                if (!response.ok) {
                    const errorText = await response.text();
                    console.error('Error response:', errorText);
                    throw new Error(`HTTP error! status: ${response.status} - ${errorText}`);
                }
                
                const result = await response.json();
                console.log('Save result:', result);
                
                // Handle the response - either update existing or add new prompt
                if (isNewPrompt) {
                    // Add new prompt to the array
                    const newPrompt = {
                        id: this.editPromptData.id,
                        name: this.editPromptData.name,
                        revision_id: this.editPromptData.revision_id,
                        status: 'active',
                        last_modified: new Date().toISOString().split('T')[0],
                        author: 'Current User',
                        size: this.editPromptData.content.length,
                        preview: this.cleanPreviewText(this.editPromptData.content),
                        file_path: filename,
                        type: 'system',
                        content: this.editPromptData.content
                    };
                    
                    this.prompts.push(newPrompt);
                    console.log('Added new prompt:', newPrompt);
                } else {
                    // Update existing prompt
                    this.prompts[existingPromptIndex] = {
                        ...this.prompts[existingPromptIndex],
                        name: this.editPromptData.name,
                        file_path: filename,
                        revision_id: this.editPromptData.revision_id,
                        size: this.editPromptData.content.length,
                        preview: this.cleanPreviewText(this.editPromptData.content),
                        content: this.editPromptData.content,
                        last_modified: new Date().toISOString().split('T')[0]
                    };
                    console.log('Updated existing prompt at index:', existingPromptIndex);
                }
                
                this.filterPrompts();
                this.lastSavedTime = new Date().toLocaleTimeString();
                
                // Close edit modal
                const editModal = bootstrap.Modal.getInstance(document.getElementById('editPromptModal'));
                if (editModal) {
                    editModal.hide();
                }
                
                const action = isNewPrompt ? 'created' : 'updated';
                alert(`Prompt "${this.editPromptData.name}" has been ${action} successfully!`);
                
            } catch (error) {
                console.error('Error saving prompt:', error);
                alert(`Error saving prompt: ${error.message}`);
            }
        },

        // Duplicate prompt
        async duplicatePrompt(prompt) {
            console.log('Duplicating prompt:', prompt.id);
            
            try {
                // TODO: Replace with actual API call
                /*
                const response = await fetch(`${PROMPTS_API_CONFIG.baseUrl}${PROMPTS_API_CONFIG.endpoints.duplicatePrompt.replace('{promptId}', prompt.id)}`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' }
                });
                
                if (!response.ok) {
                    throw new Error(`HTTP error! status: ${response.status}`);
                }
                
                const duplicatedPrompt = await response.json();
                this.prompts.push(duplicatedPrompt);
                this.filterPrompts();
                */
                
                // Simulate duplication for demo
                const duplicatedPrompt = {
                    ...prompt,
                    id: `${prompt.id}-copy-${Date.now()}`,
                    name: `${prompt.name} (Copy)`,
                    status: 'draft',
                    last_modified: new Date().toISOString().split('T')[0],
                    author: 'Current User'
                };
                
                this.prompts.push(duplicatedPrompt);
                this.filterPrompts();
                
                alert(`Prompt duplicated successfully: ${duplicatedPrompt.name}`);
            } catch (error) {
                console.error('Error duplicating prompt:', error);
                alert('Error duplicating prompt. Please try again.');
            }
        },

        // Download prompt
        downloadPrompt(prompt) {
            console.log('Downloading prompt:', prompt.id);
            
            // Create a downloadable text file
            const content = `Prompt Name: ${prompt.name}\nRevision: ${this.getRevisionName(prompt.revision_id)}\nAuthor: ${prompt.author}\nLast Modified: ${prompt.last_modified}\n\nContent:\n${prompt.preview}...`;
            
            const blob = new Blob([content], { type: 'text/plain' });
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `${prompt.name.replace(/\s+/g, '_')}.txt`;
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            window.URL.revokeObjectURL(url);
        },

        // Delete prompt
        async deletePrompt(prompt) {
            if (!confirm(`Are you sure you want to delete "${prompt.name}"? This action cannot be undone.`)) {
                return;
            }
            
            console.log('Deleting prompt:', prompt.id);
            
            try {
                // TODO: Replace with actual API call
                /*
                const response = await fetch(`${PROMPTS_API_CONFIG.baseUrl}${PROMPTS_API_CONFIG.endpoints.deletePrompt.replace('{promptId}', prompt.id)}`, {
                    method: 'DELETE'
                });
                
                if (!response.ok) {
                    throw new Error(`HTTP error! status: ${response.status}`);
                }
                */
                
                // Simulate deletion for demo
                const index = this.prompts.findIndex(p => p.id === prompt.id);
                if (index > -1) {
                    this.prompts.splice(index, 1);
                    this.filterPrompts();
                    alert(`Prompt "${prompt.name}" has been deleted.`);
                }
            } catch (error) {
                console.error('Error deleting prompt:', error);
                alert('Error deleting prompt. Please try again.');
            }
        },

        // Create new prompt
        createNewPrompt() {
            console.log('Creating new prompt');
            this.isCreatingNewPrompt = true; // Set flag for creating
            
            // Set up a new prompt with default values
            const newPromptId = `prompt-${Date.now()}`;
            const defaultRevision = this.selectedRevision === 'all' ? 
                (this.revisions.length > 0 ? this.revisions[this.revisions.length - 1].id : 'v1') : 
                this.selectedRevision;
            
            // Create new prompt object
            this.selectedPrompt = {
                id: newPromptId,
                name: '',
                revision_id: defaultRevision,
                status: 'draft',
                last_modified: new Date().toISOString().split('T')[0],
                author: 'Current User',
                size: 0,
                preview: '',
                file_path: '/prompts/new_prompt.jinja',
                type: 'system'
            };
            
            // Initialize edit data for new prompt
            this.editPromptData = {
                id: newPromptId,
                name: '',
                fileName: 'new_prompt',
                revision_id: defaultRevision,
                content: ''
            };
            
            // Show edit modal for new prompt
            const editModal = new bootstrap.Modal(document.getElementById('editPromptModal'));
            editModal.show();
        },

    };
}
