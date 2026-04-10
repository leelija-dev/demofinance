(function() {
    // Auto Pay functionality for loan management
    function getCSRFToken() {
        // Try multiple ways to get the CSRF token
        let token = null;

        // Method 1: Look for the input field
        const tokenInput = document.querySelector('[name=csrfmiddlewaretoken]');
        if (tokenInput) {
            token = tokenInput.value;
        }

        // Method 2: Look for the meta tag (common in Django templates)
        if (!token) {
            const metaToken = document.querySelector('meta[name="csrf-token"]');
            if (metaToken) {
                token = metaToken.getAttribute('content');
            }
        }

        // Method 3: Look for token in cookies
        if (!token) {
            const cookies = document.cookie.split(';');
            for (let cookie of cookies) {
                const [name, value] = cookie.trim().split('=');
                if (name === 'csrftoken') {
                    token = value;
                    break;
                }
            }
        }

        return token;
    }

    function autoPayLoan(loanRefNo) {
        if (!confirm('Are you sure you want to set up auto-payment for this loan?')) {
            return;
        }

        const csrfToken = getCSRFToken();
        const headers = {
            'Content-Type': 'application/json'
        };

        if (csrfToken) {
            headers['X-CSRFToken'] = csrfToken;
        }

        fetch(`/branch/api/loan/${loanRefNo}/auto-pay/setup/`, {
            method: 'POST',
            headers: headers
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                alert('Auto-payment setup initiated successfully!');
                location.reload(); // Refresh page to update button state
            } else {
                alert('Error: ' + data.message);
            }
        })
        .catch(error => {
            console.error('Error:', error);
            alert('An error occurred while setting up auto-payment.');
        });
    }

    function cancelAutoPay(loanRefNo) {
        if (!confirm('Are you sure you want to cancel auto-payment for this loan?')) {
            return;
        }

        const csrfToken = getCSRFToken();
        const headers = {
            'Content-Type': 'application/json'
        };

        if (csrfToken) {
            headers['X-CSRFToken'] = csrfToken;
        }

        fetch(`/branch/api/loan/${loanRefNo}/auto-pay/cancel/`, {
            method: 'POST',
            headers: headers
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                alert('Auto-payment cancelled successfully!');
                location.reload(); // Refresh page to update button state
            } else {
                alert('Error: ' + data.message);
            }
        })
        .catch(error => {
            console.error('Error:', error);
            alert('An error occurred while cancelling auto-payment.');
        });
    }

    // Make functions globally available
    window.autoPayLoan = autoPayLoan;
    window.cancelAutoPay = cancelAutoPay;
})();
