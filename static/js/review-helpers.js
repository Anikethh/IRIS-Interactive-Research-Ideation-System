/**
 * Helper functions for handling structured reviews
 */

/**
 * Finds and highlights a given text in the original content
 * @param {string} originalText - The complete original text
 * @param {string} highlightText - The text to highlight
 * @param {string} category - Category of the highlight
 * @returns {Object} The highlighted HTML and matching information
 */
function findAndHighlight(originalText, highlightText, category) {
    if (!highlightText || !originalText) {
        return {
            html: originalText,
            matched: false,
            matchedText: ''
        };
    }
    
    // Try exact match first
    if (originalText.includes(highlightText)) {
        const parts = originalText.split(highlightText);
        const html = parts.join(`<mark class="highlight" data-category="${category}">${highlightText}</mark>`);
        
        return {
            html: html,
            matched: true,
            matchedText: highlightText
        };
    }
    
    // Try case-insensitive match
    const regex = new RegExp(escapeRegExp(highlightText), 'i');
    const match = originalText.match(regex);
    
    if (match) {
        const matchedText = match[0];
        const parts = originalText.split(matchedText);
        const html = parts.join(`<mark class="highlight" data-category="${category}">${matchedText}</mark>`);
        
        return {
            html: html,
            matched: true,
            matchedText: matchedText
        };
    }
    
    // If no matches found, return the original text
    return {
        html: originalText,
        matched: false,
        matchedText: ''
    };
}

/**
 * Escapes special characters in a string for use in a RegExp
 * @param {string} string - The string to escape
 * @returns {string} The escaped string
 */
function escapeRegExp(string) {
    return string.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

/**
 * Formats a review for display
 * @param {Object} reviewData - The review data from the API
 * @returns {string} HTML formatted review
 */
function formatReview(reviewData) {
    if (!reviewData) return '';
    
    let html = `<div class="review-section">
        <h3>${reviewData.aspect.toUpperCase()}</h3>
        <div class="score">Score: ${reviewData.score}/10</div>
        <div class="summary">${reviewData.summary}</div>`;
        
    if (reviewData.highlight) {
        html += `
        <div class="highlight-section">
            <div class="highlight-category">${reviewData.highlight.category}</div>
            <div class="highlight-text">"${reviewData.highlight.text}"</div>
            <div class="highlight-review">${reviewData.highlight.review}</div>
        </div>`;
    }
    
    html += '</div>';
    return html;
}
