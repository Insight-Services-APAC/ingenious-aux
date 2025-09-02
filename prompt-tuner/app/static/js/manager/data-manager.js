/**
 * Data Manager
 * Centralized data management for dynamic workflow forms
 * Handles all form data operations, validation, and persistence
 */

class DataManager {
    constructor() {
        // Main form data storage - organized by schema
        this.formData = {};
        
        // Configuration
        this.autoSave = true;
        this.storageKey = 'dynamic_workflow_data';
    }

    /**
     * Initialize form data for a schema
     */
    initializeFormData(currentSchema, model) {
        if (!this.formData[currentSchema]) {
            this.formData[currentSchema] = {};
        }
        
        if (model.default_values) {
            Object.assign(this.formData[currentSchema], model.default_values);
        }
        
        this.saveToStorage();
    }

    /**
     * Update form data for a field
     */
    updateFormData(currentSchema, fieldName, value) {
        if (!this.formData[currentSchema]) {
            this.formData[currentSchema] = {};
        }
        
        this.formData[currentSchema][fieldName] = value;
        console.log(`DataManager: Updated form data for ${fieldName}:`, value);
        
        this.saveToStorage();
    }

    /**
     * Get form data for a specific schema
     */
    getFormDataForSchema(currentSchema) {
        return this.formData[currentSchema] || {};
    }

    /**
     * Reset form data for a schema
     */
    resetFormData(currentSchema) {
        if (currentSchema) {
            this.formData[currentSchema] = {};
        }
        this.saveToStorage();
    }

    /**
     * Clear all form data
     */
    clearAll() {
        this.formData = {};
        this.saveToStorage();
    }

    /**
     * Update nested object field data
     */
    updateNestedObjectFieldData(currentSchema, parentFieldName, propName, value) {
        if (!this.formData[currentSchema]) {
            this.formData[currentSchema] = {};
        }
        if (!this.formData[currentSchema][parentFieldName]) {
            this.formData[currentSchema][parentFieldName] = {};
        }
        
        this.formData[currentSchema][parentFieldName][propName] = value;
        console.log(`DataManager: Updated nested object field data for ${parentFieldName}.${propName}:`, value);
        
        this.saveToStorage();
    }

    /**
     * Update union field data
     */
    updateUnionFieldData(currentSchema, parentFieldName, propName, value) {
        if (!this.formData[currentSchema]) {
            this.formData[currentSchema] = {};
        }
        if (!this.formData[currentSchema][parentFieldName]) {
            this.formData[currentSchema][parentFieldName] = {};
        }
        
        this.formData[currentSchema][parentFieldName][propName] = value;
        console.log(`DataManager: Updated union field data for ${parentFieldName}.${propName}:`, value);
        
        this.saveToStorage();
    }

    /**
     * Initialize union form data
     */
    initializeUnionFormData(currentSchema, fieldName, schema) {
        if (!this.formData[currentSchema]) {
            this.formData[currentSchema] = {};
        }
        
        // Initialize with default values if not already set
        if (!this.formData[currentSchema][fieldName] || typeof this.formData[currentSchema][fieldName] !== 'object') {
            this.formData[currentSchema][fieldName] = { ...(schema.default_values || {}) };
        }
        
        this.saveToStorage();
    }

    /**
     * Add array item and return its index
     */
    addArrayItem(currentSchema, fieldName, itemData) {
        if (!this.formData[currentSchema]) {
            this.formData[currentSchema] = {};
        }
        if (!this.formData[currentSchema][fieldName]) {
            this.formData[currentSchema][fieldName] = [];
        }
        
        const itemIndex = this.formData[currentSchema][fieldName].length;
        this.formData[currentSchema][fieldName].push(itemData);
        
        console.log(`DataManager: Added array item for ${fieldName} at index ${itemIndex}:`, itemData);
        this.saveToStorage();
        
        return itemIndex;
    }

    /**
     * Update array item data
     */
    updateArrayItemData(currentSchema, fieldName, itemIndex, propName, value) {
        if (!this.formData[currentSchema]?.[fieldName]?.[itemIndex]) {
            if (!this.formData[currentSchema]) {
                this.formData[currentSchema] = {};
            }
            if (!this.formData[currentSchema][fieldName]) {
                this.formData[currentSchema][fieldName] = [];
            }
            if (!this.formData[currentSchema][fieldName][itemIndex]) {
                this.formData[currentSchema][fieldName][itemIndex] = {};
            }
        }

        // Handle special case where propName is empty (setting entire item data)
        if (propName === '') {
            this.formData[currentSchema][fieldName][itemIndex] = value;
        } else {
            this.formData[currentSchema][fieldName][itemIndex][propName] = value;
        }
        
        console.log(`DataManager: Updated array item data for ${fieldName}[${itemIndex}].${propName}:`, value);
        this.saveToStorage();
    }

    /**
     * Remove array item
     */
    removeArrayItem(currentSchema, fieldName, itemIndex) {
        if (this.formData[currentSchema]?.[fieldName]) {
            this.formData[currentSchema][fieldName].splice(itemIndex, 1);
            console.log(`DataManager: Removed array item ${itemIndex} from ${fieldName}`);
            this.saveToStorage();
        }
    }

    /**
     * Update array item nested object field data
     */
    updateArrayItemNestedObjectFieldData(currentSchema, fieldName, itemIndex, parentPropName, nestedPropName, value) {
        if (!this.formData[currentSchema]?.[fieldName]?.[itemIndex]) {
            if (!this.formData[currentSchema]) {
                this.formData[currentSchema] = {};
            }
            if (!this.formData[currentSchema][fieldName]) {
                this.formData[currentSchema][fieldName] = [];
            }
            if (!this.formData[currentSchema][fieldName][itemIndex]) {
                this.formData[currentSchema][fieldName][itemIndex] = {};
            }
        }
        if (!this.formData[currentSchema][fieldName][itemIndex][parentPropName]) {
            this.formData[currentSchema][fieldName][itemIndex][parentPropName] = {};
        }
        
        this.formData[currentSchema][fieldName][itemIndex][parentPropName][nestedPropName] = value;
        console.log(`DataManager: Updated array item nested object field data for ${fieldName}[${itemIndex}].${parentPropName}.${nestedPropName}:`, value);
        
        this.saveToStorage();
    }

    /**
     * Update array item union field data
     */
    updateArrayItemUnionFieldData(currentSchema, fieldName, itemIndex, propName, schemaPropName, value) {
        if (!this.formData[currentSchema]?.[fieldName]?.[itemIndex]) {
            if (!this.formData[currentSchema]) {
                this.formData[currentSchema] = {};
            }
            if (!this.formData[currentSchema][fieldName]) {
                this.formData[currentSchema][fieldName] = [];
            }
            if (!this.formData[currentSchema][fieldName][itemIndex]) {
                this.formData[currentSchema][fieldName][itemIndex] = {};
            }
        }
        if (!this.formData[currentSchema][fieldName][itemIndex][propName]) {
            this.formData[currentSchema][fieldName][itemIndex][propName] = {};
        }
        
        this.formData[currentSchema][fieldName][itemIndex][propName][schemaPropName] = value;
        console.log(`DataManager: Updated array item union field data for ${fieldName}[${itemIndex}].${propName}.${schemaPropName}:`, value);
        
        this.saveToStorage();
    }

    /**
     * Initialize array item union form data
     */
    initializeArrayItemUnionFormData(currentSchema, fieldName, itemIndex, propName, schema) {
        if (!this.formData[currentSchema]?.[fieldName]?.[itemIndex]) {
            if (!this.formData[currentSchema]) {
                this.formData[currentSchema] = {};
            }
            if (!this.formData[currentSchema][fieldName]) {
                this.formData[currentSchema][fieldName] = [];
            }
            if (!this.formData[currentSchema][fieldName][itemIndex]) {
                this.formData[currentSchema][fieldName][itemIndex] = {};
            }
        }
        
        // Initialize with default values if not already set
        if (!this.formData[currentSchema][fieldName][itemIndex][propName] || 
            typeof this.formData[currentSchema][fieldName][itemIndex][propName] !== 'object') {
            this.formData[currentSchema][fieldName][itemIndex][propName] = { ...(schema.default_values || {}) };
        }
        
        this.saveToStorage();
    }

    /**
     * Validate form data
     */
    validateFormData(currentSchema, validationRules = {}) {
        const data = this.getFormDataForSchema(currentSchema);
        const errors = [];
        const warnings = [];

        // Basic validation
        if (!data || Object.keys(data).length === 0) {
            errors.push('No form data found');
            return { isValid: false, errors, warnings };
        }

        // Custom validation rules
        for (const [fieldName, rules] of Object.entries(validationRules)) {
            const fieldValue = data[fieldName];
            
            if (rules.required && (!fieldValue || (Array.isArray(fieldValue) && fieldValue.length === 0))) {
                errors.push(`${fieldName} is required`);
            }
            
            if (rules.minLength && fieldValue && fieldValue.length < rules.minLength) {
                errors.push(`${fieldName} must be at least ${rules.minLength} characters`);
            }
            
            if (rules.maxLength && fieldValue && fieldValue.length > rules.maxLength) {
                warnings.push(`${fieldName} exceeds recommended length of ${rules.maxLength} characters`);
            }
        }

        return {
            isValid: errors.length === 0,
            errors,
            warnings
        };
    }

    /**
     * Export data in various formats
     */
    exportData(currentSchema, format = 'json') {
        const data = this.getFormDataForSchema(currentSchema);
        
        if (!data || Object.keys(data).length === 0) {
            throw new Error('No data to export');
        }

        const exportData = {
            timestamp: new Date().toISOString(),
            workflow_name: currentSchema,
            form_data: data
        };

        switch (format.toLowerCase()) {
            case 'json':
                return {
                    content: JSON.stringify(exportData, null, 2),
                    filename: `${currentSchema}-data-${new Date().toISOString().split('T')[0]}.json`,
                    mimeType: 'application/json'
                };
                
            case 'csv':
                // Simple CSV export for flat data
                const csvContent = this.convertToCSV(data);
                return {
                    content: csvContent,
                    filename: `${currentSchema}-data-${new Date().toISOString().split('T')[0]}.csv`,
                    mimeType: 'text/csv'
                };
                
            default:
                throw new Error(`Unsupported export format: ${format}`);
        }
    }

    /**
     * Convert data to CSV format (simplified)
     */
    convertToCSV(data) {
        const rows = [];
        const headers = new Set();
        
        // Extract all possible headers
        const extractHeaders = (obj, prefix = '') => {
            for (const [key, value] of Object.entries(obj)) {
                const header = prefix ? `${prefix}.${key}` : key;
                if (Array.isArray(value)) {
                    headers.add(header + '_count');
                    value.forEach((item, index) => {
                        if (typeof item === 'object' && item !== null) {
                            extractHeaders(item, `${header}[${index}]`);
                        }
                    });
                } else if (typeof value === 'object' && value !== null) {
                    extractHeaders(value, header);
                } else {
                    headers.add(header);
                }
            }
        };

        extractHeaders(data);
        const headerArray = Array.from(headers);
        rows.push(headerArray.join(','));

        // Extract values for CSV row
        const extractValues = (obj, prefix = '') => {
            const values = {};
            for (const [key, value] of Object.entries(obj)) {
                const header = prefix ? `${prefix}.${key}` : key;
                if (Array.isArray(value)) {
                    values[header + '_count'] = value.length;
                    value.forEach((item, index) => {
                        if (typeof item === 'object' && item !== null) {
                            Object.assign(values, extractValues(item, `${header}[${index}]`));
                        }
                    });
                } else if (typeof value === 'object' && value !== null) {
                    Object.assign(values, extractValues(value, header));
                } else {
                    values[header] = value;
                }
            }
            return values;
        };

        const values = extractValues(data);
        const row = headerArray.map(header => {
            const value = values[header];
            return value !== undefined ? `"${String(value).replace(/"/g, '""')}"` : '';
        });
        rows.push(row.join(','));

        return rows.join('\n');
    }

    /**
     * Import data from external source
     */
    importData(currentSchema, importedData, mergeStrategy = 'replace') {
        if (!importedData) {
            throw new Error('No data provided for import');
        }

        let dataToImport = importedData;
        
        // Handle different import formats
        if (typeof importedData === 'string') {
            try {
                dataToImport = JSON.parse(importedData);
            } catch (error) {
                throw new Error('Invalid JSON format');
            }
        }

        // Extract form_data if it's wrapped in export format
        if (dataToImport.form_data) {
            dataToImport = dataToImport.form_data;
        }

        switch (mergeStrategy) {
            case 'replace':
                this.formData[currentSchema] = { ...dataToImport };
                break;
                
            case 'merge':
                if (!this.formData[currentSchema]) {
                    this.formData[currentSchema] = {};
                }
                this.formData[currentSchema] = { ...this.formData[currentSchema], ...dataToImport };
                break;
                
            default:
                throw new Error(`Unsupported merge strategy: ${mergeStrategy}`);
        }

        this.saveToStorage();
        console.log(`DataManager: Imported data for ${currentSchema} using ${mergeStrategy} strategy`);
    }

    /**
     * Get data statistics
     */
    getDataStats(currentSchema) {
        const data = this.getFormDataForSchema(currentSchema);
        const stats = {
            totalFields: 0,
            filledFields: 0,
            emptyFields: 0,
            arrayFields: 0,
            objectFields: 0,
            simpleFields: 0
        };

        const analyzeObject = (obj) => {
            for (const [key, value] of Object.entries(obj)) {
                stats.totalFields++;
                
                if (value === null || value === undefined || value === '') {
                    stats.emptyFields++;
                } else {
                    stats.filledFields++;
                    
                    if (Array.isArray(value)) {
                        stats.arrayFields++;
                    } else if (typeof value === 'object') {
                        stats.objectFields++;
                        analyzeObject(value);
                    } else {
                        stats.simpleFields++;
                    }
                }
            }
        };

        analyzeObject(data);
        return stats;
    }

    /**
     * Save data to browser storage
     */
    saveToStorage() {
        if (this.autoSave && typeof Storage !== 'undefined') {
            try {
                localStorage.setItem(this.storageKey, JSON.stringify(this.formData));
            } catch (error) {
                console.warn('DataManager: Failed to save to localStorage:', error);
            }
        }
    }

    /**
     * Load data from browser storage
     */
    loadFromStorage() {
        if (typeof Storage !== 'undefined') {
            try {
                const stored = localStorage.getItem(this.storageKey);
                if (stored) {
                    this.formData = JSON.parse(stored);
                    console.log('DataManager: Loaded data from localStorage');
                }
            } catch (error) {
                console.warn('DataManager: Failed to load from localStorage:', error);
                this.formData = {};
            }
        }
    }

    /**
     * Clear storage
     */
    clearStorage() {
        if (typeof Storage !== 'undefined') {
            localStorage.removeItem(this.storageKey);
        }
    }

    /**
     * Get all form data
     */
    getAllFormData() {
        return this.formData;
    }

    /**
     * Set data directly (for testing or advanced use)
     */
    setFormData(currentSchema, data) {
        this.formData[currentSchema] = data;
        this.saveToStorage();
    }

    /**
     * Clone form data for backup
     */
    cloneFormData(currentSchema) {
        return JSON.parse(JSON.stringify(this.getFormDataForSchema(currentSchema)));
    }
}

// Global instance for easy access
window.dataManager = new DataManager();

// Auto-load from storage when script loads
document.addEventListener('DOMContentLoaded', () => {
    if (window.dataManager) {
        window.dataManager.loadFromStorage();
    }
});

// Export for use in other modules
window.DataManager = DataManager;