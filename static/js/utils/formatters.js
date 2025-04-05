
export function formatMessage(content) {
    try {
        return marked.parse(content);
    } catch (e) {
        console.error('Markdown parsing error:', e);
        return content;
    }
}

// Helper function to escape special characters for RegExp
export function escapeRegExp(string) {
    return string.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

// Helper function to escape HTML special characters
export function escape(str) {
    const div = document.createElement('div');
    div.appendChild(document.createTextNode(str));
    return div.innerHTML;
}

// Helper function to unescape HTML special characters
export function unescape(str) {
    const div = document.createElement('div');
    div.innerHTML = str;
    return div.textContent;
}
