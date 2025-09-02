/**
 * DisplayUtils - UI formatting and display utilities
 * Provides consistent formatting for status badges, workflow names, and other UI elements
 */
class DisplayUtils {
    /**
     * Get status badge CSS class based on status
     * @param {string} status - Status string
     * @returns {string} CSS class for badge
     */
    static getStatusBadgeClass(status) {
        if (!status) return 'bg-secondary';
        
        const normalizedStatus = status.toLowerCase().trim();
        
        switch (normalizedStatus) {
            case 'active':
            case 'running':
            case 'success':
            case 'completed':
            case 'online':
                return 'bg-success';
            case 'inactive':
            case 'stopped':
            case 'failed':
            case 'error':
            case 'offline':
                return 'bg-danger';
            case 'pending':
            case 'waiting':
            case 'processing':
            case 'loading':
                return 'bg-warning';
            case 'draft':
            case 'development':
            case 'staging':
                return 'bg-info';
            case 'production':
            case 'live':
                return 'bg-primary';
            case 'unknown':
            case 'unavailable':
            default:
                return 'bg-secondary';
        }
    }

    /**
     * Format status text for display
     * @param {string} status - Raw status string
     * @returns {string} Formatted status text
     */
    static formatStatus(status) {
        if (!status) return 'Unknown';
        
        return status
            .replace(/[_-]/g, ' ')
            .replace(/\b\w/g, l => l.toUpperCase())
            .trim();
    }

    /**
     * Get agent status CSS class
     * @param {string} agentType - Agent type or status
     * @returns {string} CSS class for agent status
     */
    static getAgentStatusClass(agentType) {
        if (!agentType) return 'text-secondary';
        
        const normalizedType = agentType.toLowerCase().trim();
        
        switch (normalizedType) {
            case 'coordinator':
            case 'manager':
            case 'orchestrator':
                return 'text-primary';
            case 'processor':
            case 'worker':
            case 'executor':
                return 'text-success';
            case 'validator':
            case 'checker':
            case 'reviewer':
                return 'text-info';
            case 'analyzer':
            case 'evaluator':
            case 'assessor':
                return 'text-warning';
            default:
                return 'text-secondary';
        }
    }

    /**
     * Format workflow name for display
     * @param {string} workflowName - Raw workflow name
     * @returns {string} Formatted workflow name
     */
    static formatWorkflowName(workflowName) {
        if (!workflowName) return 'Unnamed Workflow';
        
        return workflowName
            .replace(/[-_]/g, ' ')
            .replace(/\b\w/g, l => l.toUpperCase())
            .trim();
    }

    /**
     * Format version text to proper case
     * @param {string} version - Version string
     * @returns {string} Formatted version
     */
    static formatVersionText(version) {
        if (!version) return 'Unknown Version';
        
        // Handle semantic versions (e.g., "1.0.0")
        if (/^\d+\.\d+\.\d+/.test(version)) {
            return `v${version}`;
        }
        
        // Handle word versions (e.g., "latest", "production")
        return version
            .replace(/[-_]/g, ' ')
            .replace(/\b\w/g, l => l.toUpperCase())
            .trim();
    }

    /**
     * Get model icon based on model type or name
     * @param {string} modelType - Model type or name
     * @returns {string} Font Awesome icon class
     */
    static getModelIcon(modelType) {
        if (!modelType) return 'fas fa-cube';
        
        const normalizedType = modelType.toLowerCase().trim();
        
        if (normalizedType.includes('user') || normalizedType.includes('person')) {
            return 'fas fa-user';
        }
        if (normalizedType.includes('store') || normalizedType.includes('shop')) {
            return 'fas fa-store';
        }
        if (normalizedType.includes('bike') || normalizedType.includes('bicycle')) {
            return 'fas fa-bicycle';
        }
        if (normalizedType.includes('order') || normalizedType.includes('purchase')) {
            return 'fas fa-shopping-cart';
        }
        if (normalizedType.includes('location') || normalizedType.includes('address')) {
            return 'fas fa-map-marker-alt';
        }
        if (normalizedType.includes('product') || normalizedType.includes('item')) {
            return 'fas fa-box';
        }
        if (normalizedType.includes('config') || normalizedType.includes('setting')) {
            return 'fas fa-cog';
        }
        if (normalizedType.includes('data') || normalizedType.includes('record')) {
            return 'fas fa-database';
        }
        
        return 'fas fa-cube';
    }

    /**
     * Get section icon based on field name or section type
     * @param {string} fieldName - Field name or section identifier
     * @returns {string} Font Awesome icon class
     */
    static getSectionIcon(fieldName) {
        if (!fieldName) return 'fas fa-list';
        
        const normalizedName = fieldName.toLowerCase().trim();
        
        if (normalizedName.includes('basic') || normalizedName.includes('general')) {
            return 'fas fa-info-circle';
        }
        if (normalizedName.includes('advanced') || normalizedName.includes('detail')) {
            return 'fas fa-cogs';
        }
        if (normalizedName.includes('contact') || normalizedName.includes('communication')) {
            return 'fas fa-envelope';
        }
        if (normalizedName.includes('address') || normalizedName.includes('location')) {
            return 'fas fa-map-marker-alt';
        }
        if (normalizedName.includes('preference') || normalizedName.includes('setting')) {
            return 'fas fa-sliders-h';
        }
        if (normalizedName.includes('security') || normalizedName.includes('auth')) {
            return 'fas fa-shield-alt';
        }
        if (normalizedName.includes('billing') || normalizedName.includes('payment')) {
            return 'fas fa-credit-card';
        }
        
        return 'fas fa-list';
    }

    /**
     * Format field label from camelCase or snake_case
     * @param {string} fieldName - Field name to format
     * @returns {string} Formatted label
     */
    static formatFieldLabel(fieldName) {
        if (!fieldName) return '';
        
        return fieldName
            .replace(/([a-z])([A-Z])/g, '$1 $2') // camelCase to words
            .replace(/[_-]/g, ' ') // snake_case/kebab-case to words
            .replace(/\b\w/g, l => l.toUpperCase()) // capitalize first letter of each word
            .trim();
    }

    /**
     * Format enum label for display
     * @param {string} enumValue - Enum value
     * @returns {string} Formatted enum label
     */
    static formatEnumLabel(enumValue) {
        if (!enumValue) return '';
        
        return enumValue
            .replace(/[_-]/g, ' ')
            .replace(/\b\w/g, l => l.toUpperCase())
            .trim();
    }

    /**
     * Get progress bar class based on percentage
     * @param {number} percentage - Progress percentage (0-100)
     * @returns {string} Bootstrap progress bar class
     */
    static getProgressBarClass(percentage) {
        if (percentage >= 100) return 'bg-success';
        if (percentage >= 75) return 'bg-info';
        if (percentage >= 50) return 'bg-warning';
        if (percentage >= 25) return 'bg-danger';
        return 'bg-secondary';
    }

    /**
     * Format file size for display
     * @param {number} bytes - File size in bytes
     * @returns {string} Formatted file size
     */
    static formatFileSize(bytes) {
        if (bytes === 0) return '0 B';
        
        const k = 1024;
        const sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        
        return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
    }

    /**
     * Format date for display
     * @param {string|Date} date - Date to format
     * @param {string} format - Format type ('short', 'long', 'relative')
     * @returns {string} Formatted date
     */
    static formatDate(date, format = 'short') {
        if (!date) return 'Unknown Date';
        
        const dateObj = new Date(date);
        if (isNaN(dateObj.getTime())) return 'Invalid Date';
        
        switch (format) {
            case 'long':
                return dateObj.toLocaleDateString('en-US', {
                    year: 'numeric',
                    month: 'long',
                    day: 'numeric',
                    hour: '2-digit',
                    minute: '2-digit'
                });
            case 'relative':
                return this.formatRelativeTime(dateObj);
            case 'short':
            default:
                return dateObj.toLocaleDateString('en-US', {
                    year: 'numeric',
                    month: 'short',
                    day: 'numeric'
                });
        }
    }

    /**
     * Format relative time (e.g., "2 hours ago")
     * @param {Date} date - Date to format
     * @returns {string} Relative time string
     */
    static formatRelativeTime(date) {
        const now = new Date();
        const diffMs = now - date;
        const diffSecs = Math.floor(diffMs / 1000);
        const diffMins = Math.floor(diffSecs / 60);
        const diffHours = Math.floor(diffMins / 60);
        const diffDays = Math.floor(diffHours / 24);

        if (diffSecs < 60) return 'Just now';
        if (diffMins < 60) return `${diffMins} minute${diffMins > 1 ? 's' : ''} ago`;
        if (diffHours < 24) return `${diffHours} hour${diffHours > 1 ? 's' : ''} ago`;
        if (diffDays < 30) return `${diffDays} day${diffDays > 1 ? 's' : ''} ago`;
        
        return date.toLocaleDateString();
    }

    /**
     * Truncate text with ellipsis
     * @param {string} text - Text to truncate
     * @param {number} maxLength - Maximum length
     * @param {string} suffix - Suffix to add (default: '...')
     * @returns {string} Truncated text
     */
    static truncateText(text, maxLength, suffix = '...') {
        if (!text || text.length <= maxLength) return text || '';
        
        return text.substring(0, maxLength - suffix.length) + suffix;
    }

    /**
     * Generate a contrasting text color based on background color
     * @param {string} backgroundColor - Background color (hex)
     * @returns {string} Text color ('black' or 'white')
     */
    static getContrastTextColor(backgroundColor) {
        if (!backgroundColor) return 'black';
        
        // Remove # if present
        const hex = backgroundColor.replace('#', '');
        
        // Convert to RGB
        const r = parseInt(hex.substr(0, 2), 16);
        const g = parseInt(hex.substr(2, 2), 16);
        const b = parseInt(hex.substr(4, 2), 16);
        
        // Calculate luminance
        const luminance = (0.299 * r + 0.587 * g + 0.114 * b) / 255;
        
        return luminance > 0.5 ? 'black' : 'white';
    }

    /**
     * Show toast notification
     * @param {string} message - Message to display
     * @param {string} type - Toast type (success, error, warning, info)
     * @param {number} duration - Duration in milliseconds
     */
    static showToast(message, type = 'info', duration = 3000) {
        const toastContainer = this.getOrCreateToastContainer();
        
        const toast = document.createElement('div');
        toast.className = `toast align-items-center text-white bg-${type === 'error' ? 'danger' : type} border-0 show`;
        toast.setAttribute('role', 'alert');
        toast.setAttribute('aria-live', 'assertive');
        toast.setAttribute('aria-atomic', 'true');
        
        toast.innerHTML = `
            <div class="d-flex">
                <div class="toast-body">
                    ${message}
                </div>
                <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast"></button>
            </div>
        `;
        
        toastContainer.appendChild(toast);
        
        // Auto-remove after duration
        setTimeout(() => {
            if (toast.parentNode) {
                toast.parentNode.removeChild(toast);
            }
        }, duration);
        
        return toast;
    }

    /**
     * Get or create toast container
     * @returns {HTMLElement} Toast container element
     */
    static getOrCreateToastContainer() {
        let container = document.getElementById('toast-container');
        if (!container) {
            container = document.createElement('div');
            container.id = 'toast-container';
            container.className = 'toast-container position-fixed top-0 end-0 p-3';
            container.style.zIndex = '9999';
            document.body.appendChild(container);
        }
        return container;
    }
}

// Export for both CommonJS and ES6 modules
if (typeof module !== 'undefined' && module.exports) {
    module.exports = DisplayUtils;
} else if (typeof window !== 'undefined') {
    window.DisplayUtils = DisplayUtils;
}