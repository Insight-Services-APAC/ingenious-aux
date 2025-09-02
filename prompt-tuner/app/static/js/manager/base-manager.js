/**
 * BaseManager - Abstract base class with common utilities
 * Provides shared functionality for all manager classes
 */
class BaseManager {
    /**
     * Format field name to readable label
     * @param {string} fieldName - Raw field name
     * @returns {string} Formatted field name
     */
    static formatFieldName(fieldName) {
        if (!fieldName) return '';
        
        return fieldName
            .replace(/([A-Z])/g, ' $1')
            .replace(/^./, str => str.toUpperCase())
            .replace(/_/g, ' ')
            .trim();
    }

    /**
     * Sanitize field name from label text
     * @param {string} labelText - Label text to sanitize
     * @returns {string} Sanitized field name
     */
    static sanitizeFieldName(labelText) {
        if (!labelText) return '';
        
        return labelText
            .toLowerCase()
            .replace(/[^a-zA-Z0-9]/g, '_')
            .replace(/_+/g, '_')
            .replace(/^_|_$/g, '');
    }

    /**
     * Clean display name utility
     * @param {string} name - Name to clean
     * @returns {string} Cleaned name
     */
    static cleanDisplayName(name) {
        if (!name) return '';
        
        return name
            // Remove "RootModel" prefix and any trailing underscores
            .replace(/^RootModel[_-]?/i, '')
            // Remove other common prefixes
            .replace(/^(Model|Schema|Type)[_-]?/i, '')
            // Convert camelCase to spaces
            .replace(/([a-z])([A-Z])/g, '$1 $2')
            // Replace underscores and hyphens with spaces
            .replace(/[_-]/g, ' ')
            // Remove multiple spaces
            .replace(/\s+/g, ' ')
            // Capitalize first letter of each word
            .replace(/\b\w/g, l => l.toUpperCase())
            .trim();
    }

    /**
     * Parse field name from DOM element ID
     * @param {string} id - DOM element ID
     * @returns {string} Parsed field name
     */
    static parseFieldNameFromId(id) {
        if (!id) return '';
        
        // Handle various ID patterns like form_field_name, schema-field-name, etc.
        const parts = id.split(/[-_]/);
        if (parts.length > 2) {
            return parts.slice(2).join('_'); // Remove prefix like 'form_field_'
        }
        return parts[parts.length - 1] || '';
    }

    /**
     * Set nested value in object using dot notation
     * @param {Object} obj - Target object
     * @param {string} path - Dot notation path (e.g., 'user.profile.name')
     * @param {*} value - Value to set
     */
    static setNestedValue(obj, path, value) {
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
     * Get nested value from object using dot notation
     * @param {Object} obj - Source object
     * @param {string} path - Dot notation path
     * @returns {*} Retrieved value
     */
    static getNestedValue(obj, path) {
        return path.split('.').reduce((current, key) => {
            return current && current[key] !== undefined ? current[key] : undefined;
        }, obj);
    }

    /**
     * Show message to user
     * @param {string} message - Message to display
     * @param {string} type - Message type (success, error, warning, info)
     */
    static showMessage(message, type = 'info') {
        // Create a simple toast notification
        const toast = document.createElement('div');
        toast.className = `alert alert-${type} position-fixed top-0 end-0 m-3`;
        toast.style.zIndex = '9999';
        toast.textContent = message;
        
        document.body.appendChild(toast);
        
        // Auto-remove after 3 seconds
        setTimeout(() => {
            if (toast.parentNode) {
                toast.parentNode.removeChild(toast);
            }
        }, 3000);
    }

    /**
     * Logging utility with level control
     * @param {*} message - Message to log
     * @param {string} level - Log level (debug, info, warn, error)
     */
    static log(message, level = 'info') {
        const timestamp = new Date().toISOString();
        const prefix = `[${timestamp}] [${level.toUpperCase()}]`;
        
        switch (level) {
            case 'debug':
                console.debug(prefix, message);
                break;
            case 'warn':
                console.warn(prefix, message);
                break;
            case 'error':
                console.error(prefix, message);
                break;
            default:
                console.log(prefix, message);
        }
    }

    /**
     * Deep clone an object
     * @param {*} obj - Object to clone
     * @returns {*} Cloned object
     */
    static deepClone(obj) {
        if (obj === null || typeof obj !== 'object') return obj;
        if (obj instanceof Date) return new Date(obj.getTime());
        if (obj instanceof Array) return obj.map(item => this.deepClone(item));
        
        const cloned = {};
        for (let key in obj) {
            if (obj.hasOwnProperty(key)) {
                cloned[key] = this.deepClone(obj[key]);
            }
        }
        return cloned;
    }

    /**
     * Debounce function calls
     * @param {Function} func - Function to debounce
     * @param {number} wait - Wait time in milliseconds
     * @returns {Function} Debounced function
     */
    static debounce(func, wait) {
        let timeout;
        return function executedFunction(...args) {
            const later = () => {
                clearTimeout(timeout);
                func(...args);
            };
            clearTimeout(timeout);
            timeout = setTimeout(later, wait);
        };
    }

    /**
     * Generate unique ID
     * @param {string} prefix - Optional prefix
     * @returns {string} Unique ID
     */
    static generateUniqueId(prefix = 'id') {
        return `${prefix}_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
    }
}

// Export for both CommonJS and ES6 modules
if (typeof module !== 'undefined' && module.exports) {
    module.exports = BaseManager;
} else if (typeof window !== 'undefined') {
    window.BaseManager = BaseManager;
}