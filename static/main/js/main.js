
// submitting loader js 
const fullPageLoader = document.getElementById('full-page-loader');

// Show loader function
function showLoader() {
    fullPageLoader.style.display = 'flex';
    document.body.style.overflow = 'hidden';
}

// Hide loader function
function hideLoader() {
    fullPageLoader.style.display = 'none';
    document.body.style.overflow = '';
}

document.addEventListener('DOMContentLoaded', function() {

    document.querySelectorAll('.password-toggle').forEach(button => {
        button.addEventListener('click', function(event) {
            if (event) {
                event.preventDefault();
                // If other scripts also bind to the same button, avoid double-toggling.
                event.stopImmediatePropagation();
            }

            const targetName = (this.getAttribute('data-target') || '').trim();
            if (!targetName) return;

            // Prefer Django's default id convention: id_<field_name>
            const closestContainer = this.closest('.relative') || this.parentElement;
            const input =
                document.querySelector(`#id_${targetName}`) ||
                document.querySelector(`input[name="${targetName}"]`) ||
                (closestContainer ? closestContainer.querySelector('input') : null);
            const icon = this.querySelector('svg');
            if (!input || !icon) return;
            
            if (input.type === 'password') {
                input.type = 'text';
                // Update icon to show eye with slash
                icon.innerHTML = `
                    <path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19m-6.72-1.07a3 3 0 1 1-4.24-4.24"/>
                    <path d="M1 1l22 22"/>
                `;
            } else {
                input.type = 'password';
                // Update icon back to normal eye
                icon.innerHTML = `
                    <path d="M1 12s4-7 11-7 11 7 11 7-4 7-11 7S1 12 1 12z"></path>
                    <circle cx="12" cy="12" r="3"></circle>
                `;
            }
        });
    });
});