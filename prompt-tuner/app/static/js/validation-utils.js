/**
 * ValidationUtils - Form validation utilities
 * Provides consistent validation methods for forms, fields, and data
 */
class ValidationUtils {
    /**
     * Validate a single field based on its definition
     * @param {*} value - Field value to validate
     * @param {Object} fieldDef - Field definition with validation rules
     * @returns {Object} Validation result with isValid and errors
     */
    static validateField(value, fieldDef) {
        const result = {
            isValid: true,
            errors: []
        };

        if (!fieldDef) {
            return result;
        }

        const { required, type, minLength, maxLength, min, max, pattern, enum: enumValues } = fieldDef;

        // Required field validation
        if (required && this.isEmpty(value)) {
            result.isValid = false;
            result.errors.push('This field is required');
            return result; // Don't continue validation if required field is empty
        }

        // Skip other validations if field is empty and not required
        if (this.isEmpty(value)) {
            return result;
        }

        // Type validation
        if (type && !this.validateType(value, type)) {
            result.isValid = false;
            result.errors.push(`Invalid ${type} format`);
        }

        // String length validation
        if (type === 'string' && typeof value === 'string') {
            if (minLength && value.length < minLength) {
                result.isValid = false;
                result.errors.push(`Minimum length is ${minLength} characters`);
            }
            if (maxLength && value.length > maxLength) {
                result.isValid = false;
                result.errors.push(`Maximum length is ${maxLength} characters`);
            }
        }

        // Number range validation
        if ((type === 'number' || type === 'integer') && typeof value === 'number') {
            if (min !== undefined && value < min) {
                result.isValid = false;
                result.errors.push(`Minimum value is ${min}`);
            }
            if (max !== undefined && value > max) {
                result.isValid = false;
                result.errors.push(`Maximum value is ${max}`);
            }
        }

        // Pattern validation
        if (pattern && typeof value === 'string') {
            const regex = new RegExp(pattern);
            if (!regex.test(value)) {
                result.isValid = false;
                result.errors.push('Invalid format');
            }
        }

        // Enum validation
        if (enumValues && Array.isArray(enumValues)) {
            if (!enumValues.includes(value)) {
                result.isValid = false;
                result.errors.push('Invalid option selected');
            }
        }

        return result;
    }

    /**
     * Validate an entire form
     * @param {Object} formData - Form data to validate
     * @param {Object} schema - Schema with field definitions
     * @returns {Object} Validation result with isValid, errors, and fieldErrors
     */
    static validateForm(formData, schema) {
        const result = {
            isValid: true,
            errors: [],
            fieldErrors: {}
        };

        if (!schema || !schema.properties) {
            return result;
        }

        // Validate each field
        Object.entries(schema.properties).forEach(([fieldName, fieldDef]) => {
            const fieldValue = formData[fieldName];
            const fieldResult = this.validateField(fieldValue, fieldDef);

            if (!fieldResult.isValid) {
                result.isValid = false;
                result.fieldErrors[fieldName] = fieldResult.errors;
                result.errors.push(...fieldResult.errors.map(error => `${fieldName}: ${error}`));
            }
        });

        // Check required fields that might not be in formData
        if (schema.required && Array.isArray(schema.required)) {
            schema.required.forEach(fieldName => {
                if (!formData.hasOwnProperty(fieldName) || this.isEmpty(formData[fieldName])) {
                    result.isValid = false;
                    if (!result.fieldErrors[fieldName]) {
                        result.fieldErrors[fieldName] = [];
                    }
                    result.fieldErrors[fieldName].push('This field is required');
                    result.errors.push(`${fieldName}: This field is required`);
                }
            });
        }

        return result;
    }

    /**
     * Check if a field is required based on field definition
     * @param {Object} fieldDef - Field definition
     * @returns {boolean} True if field is required
     */
    static isFieldRequired(fieldDef) {
        if (!fieldDef) return false;
        return fieldDef.required === true;
    }

    /**
     * Validate field type
     * @param {*} value - Value to validate
     * @param {string} type - Expected type
     * @returns {boolean} True if type is valid
     */
    static validateType(value, type) {
        switch (type) {
            case 'string':
                return typeof value === 'string';
            case 'number':
                return typeof value === 'number' && !isNaN(value);
            case 'integer':
                return Number.isInteger(value);
            case 'boolean':
                return typeof value === 'boolean';
            case 'array':
                return Array.isArray(value);
            case 'object':
                return typeof value === 'object' && value !== null && !Array.isArray(value);
            case 'email':
                return this.isValidEmail(value);
            case 'url':
                return this.isValidUrl(value);
            case 'date':
                return this.isValidDate(value);
            case 'time':
                return this.isValidTime(value);
            default:
                return true; // Unknown types pass validation
        }
    }

    /**
     * Check if value is empty
     * @param {*} value - Value to check
     * @returns {boolean} True if empty
     */
    static isEmpty(value) {
        if (value === null || value === undefined) return true;
        if (typeof value === 'string') return value.trim() === '';
        if (Array.isArray(value)) return value.length === 0;
        if (typeof value === 'object') return Object.keys(value).length === 0;
        return false;
    }

    /**
     * Validate email format
     * @param {string} email - Email to validate
     * @returns {boolean} True if valid email
     */
    static isValidEmail(email) {
        if (typeof email !== 'string') return false;
        const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
        return emailRegex.test(email);
    }

    /**
     * Validate URL format
     * @param {string} url - URL to validate
     * @returns {boolean} True if valid URL
     */
    static isValidUrl(url) {
        if (typeof url !== 'string') return false;
        try {
            new URL(url);
            return true;
        } catch {
            return false;
        }
    }

    /**
     * Validate date format
     * @param {string} date - Date string to validate
     * @returns {boolean} True if valid date
     */
    static isValidDate(date) {
        if (typeof date !== 'string') return false;
        const dateObj = new Date(date);
        return !isNaN(dateObj.getTime());
    }

    /**
     * Validate time format (HH:MM or HH:MM:SS)
     * @param {string} time - Time string to validate
     * @returns {boolean} True if valid time
     */
    static isValidTime(time) {
        if (typeof time !== 'string') return false;
        const timeRegex = /^([01]?[0-9]|2[0-3]):[0-5][0-9](:[0-5][0-9])?$/;
        return timeRegex.test(time);
    }

    /**
     * Generate HTML5 validation attributes for a field
     * @param {Object} fieldDef - Field definition
     * @returns {Object} HTML attributes object
     */
    static generateValidationAttributes(fieldDef) {
        const attributes = {};

        if (!fieldDef) return attributes;

        const { required, type, minLength, maxLength, min, max, pattern } = fieldDef;

        if (required) {
            attributes.required = true;
        }

        if (type) {
            switch (type) {
                case 'email':
                    attributes.type = 'email';
                    break;
                case 'url':
                    attributes.type = 'url';
                    break;
                case 'number':
                case 'integer':
                    attributes.type = 'number';
                    break;
                case 'date':
                    attributes.type = 'date';
                    break;
                case 'time':
                    attributes.type = 'time';
                    break;
                default:
                    attributes.type = 'text';
            }
        }

        if (minLength !== undefined) {
            attributes.minlength = minLength;
        }

        if (maxLength !== undefined) {
            attributes.maxlength = maxLength;
        }

        if (min !== undefined) {
            attributes.min = min;
        }

        if (max !== undefined) {
            attributes.max = max;
        }

        if (pattern) {
            attributes.pattern = pattern;
        }

        return attributes;
    }

    /**
     * Validate schema integrity
     * @param {Object} schema - Schema to validate
     * @returns {Object} Validation result
     */
    static validateSchemaIntegrity(schema) {
        const result = {
            isValid: true,
            errors: [],
            warnings: []
        };

        if (!schema) {
            result.isValid = false;
            result.errors.push('Schema is required');
            return result;
        }

        if (typeof schema !== 'object') {
            result.isValid = false;
            result.errors.push('Schema must be an object');
            return result;
        }

        // Check for properties
        if (!schema.properties) {
            result.warnings.push('Schema has no properties defined');
        } else if (typeof schema.properties !== 'object') {
            result.isValid = false;
            result.errors.push('Schema properties must be an object');
        }

        // Check for required fields
        if (schema.required && !Array.isArray(schema.required)) {
            result.isValid = false;
            result.errors.push('Schema required field must be an array');
        }

        // Validate each property definition
        if (schema.properties) {
            Object.entries(schema.properties).forEach(([fieldName, fieldDef]) => {
                if (typeof fieldDef !== 'object') {
                    result.errors.push(`Property ${fieldName} definition must be an object`);
                    result.isValid = false;
                }

                // Check for valid type
                if (fieldDef.type) {
                    const validTypes = ['string', 'number', 'integer', 'boolean', 'array', 'object', 'email', 'url', 'date', 'time'];
                    if (!validTypes.includes(fieldDef.type)) {
                        result.warnings.push(`Property ${fieldName} has unknown type: ${fieldDef.type}`);
                    }
                }

                // Check for circular references in object properties
                if (fieldDef.type === 'object' && fieldDef.properties) {
                    this.checkCircularReferences(fieldDef.properties, [fieldName], result);
                }
            });
        }

        return result;
    }

    /**
     * Check for circular references in schema
     * @param {Object} properties - Properties to check
     * @param {Array} path - Current path
     * @param {Object} result - Result object to update
     */
    static checkCircularReferences(properties, path, result) {
        Object.entries(properties).forEach(([fieldName, fieldDef]) => {
            if (path.includes(fieldName)) {
                result.warnings.push(`Potential circular reference detected: ${path.join(' -> ')} -> ${fieldName}`);
            } else if (fieldDef.type === 'object' && fieldDef.properties) {
                this.checkCircularReferences(fieldDef.properties, [...path, fieldName], result);
            }
        });
    }

    /**
     * Sanitize input value based on type
     * @param {*} value - Value to sanitize
     * @param {string} type - Expected type
     * @returns {*} Sanitized value
     */
    static sanitizeValue(value, type) {
        if (value === null || value === undefined) {
            return value;
        }

        switch (type) {
            case 'string':
                return String(value).trim();
            case 'number':
                const num = Number(value);
                return isNaN(num) ? null : num;
            case 'integer':
                const int = parseInt(value, 10);
                return isNaN(int) ? null : int;
            case 'boolean':
                if (typeof value === 'boolean') return value;
                if (typeof value === 'string') {
                    return value.toLowerCase() === 'true' || value === '1';
                }
                return Boolean(value);
            case 'array':
                return Array.isArray(value) ? value : [value];
            case 'email':
                return typeof value === 'string' ? value.toLowerCase().trim() : value;
            case 'url':
                return typeof value === 'string' ? value.trim() : value;
            default:
                return value;
        }
    }

    /**
     * Get validation error messages for a field
     * @param {string} fieldName - Field name
     * @param {Array} errors - Array of error messages
     * @returns {string} HTML string with error messages
     */
    static getErrorMessagesHtml(fieldName, errors) {
        if (!errors || errors.length === 0) {
            return '';
        }

        const errorList = errors.map(error => `<li>${error}</li>`).join('');
        return `<div class="invalid-feedback d-block"><ul class="mb-0">${errorList}</ul></div>`;
    }

    /**
     * Show field validation error
     * @param {HTMLElement} fieldElement - Field element
     * @param {Array} errors - Array of error messages
     */
    static showFieldError(fieldElement, errors) {
        if (!fieldElement) return;

        // Remove existing error messages
        const existingError = fieldElement.parentNode.querySelector('.invalid-feedback');
        if (existingError) {
            existingError.remove();
        }

        // Add error class
        fieldElement.classList.add('is-invalid');
        fieldElement.classList.remove('is-valid');

        // Add error messages
        if (errors && errors.length > 0) {
            const errorHtml = this.getErrorMessagesHtml(fieldElement.name, errors);
            fieldElement.insertAdjacentHTML('afterend', errorHtml);
        }
    }

    /**
     * Show field validation success
     * @param {HTMLElement} fieldElement - Field element
     */
    static showFieldSuccess(fieldElement) {
        if (!fieldElement) return;

        // Remove existing error messages
        const existingError = fieldElement.parentNode.querySelector('.invalid-feedback');
        if (existingError) {
            existingError.remove();
        }

        // Add success class
        fieldElement.classList.add('is-valid');
        fieldElement.classList.remove('is-invalid');
    }

    /**
     * Clear field validation state
     * @param {HTMLElement} fieldElement - Field element
     */
    static clearFieldValidation(fieldElement) {
        if (!fieldElement) return;

        fieldElement.classList.remove('is-valid', 'is-invalid');
        
        const existingError = fieldElement.parentNode.querySelector('.invalid-feedback');
        if (existingError) {
            existingError.remove();
        }
    }

    /**
     * Validate form in real-time
     * @param {HTMLFormElement} formElement - Form element
     * @param {Object} schema - Schema for validation
     * @returns {Function} Cleanup function
     */
    static enableRealTimeValidation(formElement, schema) {
        if (!formElement || !schema) return () => {};

        const handleFieldValidation = (event) => {
            const field = event.target;
            const fieldName = field.name;
            const fieldValue = field.value;

            if (fieldName && schema.properties && schema.properties[fieldName]) {
                const fieldDef = schema.properties[fieldName];
                const validationResult = this.validateField(fieldValue, fieldDef);

                if (validationResult.isValid) {
                    this.showFieldSuccess(field);
                } else {
                    this.showFieldError(field, validationResult.errors);
                }
            }
        };

        // Add event listeners
        formElement.addEventListener('input', handleFieldValidation);
        formElement.addEventListener('blur', handleFieldValidation, true);

        // Return cleanup function
        return () => {
            formElement.removeEventListener('input', handleFieldValidation);
            formElement.removeEventListener('blur', handleFieldValidation, true);
        };
    }
}

// Export for both CommonJS and ES6 modules
if (typeof module !== 'undefined' && module.exports) {
    module.exports = ValidationUtils;
} else if (typeof window !== 'undefined') {
    window.ValidationUtils = ValidationUtils;
}