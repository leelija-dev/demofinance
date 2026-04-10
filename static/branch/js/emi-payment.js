// static/branch/js/emi-payment.js

// Utility: get CSRF token from cookies
function getCookie(name) {
    const value = `; ${document.cookie}`;
    const parts = value.split(`; ${name}=`);
    if (parts.length === 2) return parts.pop().split(';').shift();
    return null;
  }
  
  // Exported: format date as DD/MM/YYYY
  function formatDate(dateString) {
    if (!dateString) return '-';
    const date = new Date(dateString);
    if (Number.isNaN(date.getTime())) return '-';
    const day = String(date.getDate()).padStart(2, '0');
    const month = String(date.getMonth() + 1).padStart(2, '0');
    const year = date.getFullYear();
    return `${day}/${month}/${year}`;
  }
  window.formatDate = formatDate;
  
  // Exported: toggle Save visibility
  window.toggleSaveButton = function(elementId, selectedValue) {
    const btn = document.getElementById(`save-btn-${elementId}`);
    if (!btn) return;
    if (selectedValue) btn.classList.remove('hidden');
    else btn.classList.add('hidden');
  };
  
  // Exported: reflect assigned agent UI state
  function updateAgentAssignmentUI(elementId, agentName = null) {
    const agentDisplay = document.getElementById(`agent-display-${elementId}`);
    const agentSelect = document.getElementById(`agent-select-${elementId}`);
    const saveBtn = document.getElementById(`save-btn-${elementId}`);
    if (!agentDisplay || !agentSelect || !saveBtn) return;

    if (agentName) {
      agentDisplay.innerHTML = `
        <div class="flex items-center space-x-2">
          <span>${agentName}</span>
          <button onclick="editAgentAssignment('${elementId}')"
                  class="ml-2 text-blue-600 hover:text-blue-800 text-sm transition-opacity opacity-60 hover:opacity-100">
            <i class="fas fa-edit"></i>
          </button>
        </div>
      `;
      agentDisplay.classList.remove('hidden');
      // If config requests to keep select visible, do not hide it
      const keepVisible = !!(window.EMI_PAYMENT_CONFIG && window.EMI_PAYMENT_CONFIG.keepSelectVisible);
      if (!keepVisible) {
        agentSelect.classList.add('hidden');
      } else {
        agentSelect.classList.remove('hidden');
      }
      saveBtn.classList.add('hidden');

      // Ensure trash (unassign) icon is present immediately after assign
      const container = agentSelect.parentElement; // flex container beside select
      if (container && !container.querySelector(`button[data-unassign-for="${elementId}"]`)) {
        const numericEmiId = String(elementId).split('-').pop();
        const btn = document.createElement('button');
        btn.type = 'button';
        btn.title = 'Unassign agent';
        btn.setAttribute('data-unassign-for', elementId);
        btn.className = 'inline-flex items-center p-1 ml-0 rounded-md text-red-600 hover:text-red-700';
        btn.innerHTML = `
          <svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4" viewBox="0 0 24 24"
               onclick="openUnassignPopover(${numericEmiId}, this)"
               fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <polyline points="3 6 5 6 21 6" />
            <path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6" />
            <path d="M10 11v6" />
            <path d="M14 11v6" />
            <path d="M9 6V4a2 2 0 0 1 2-2h2a2 2 0 0 1 2 2v2" />
          </svg>
          <span class="sr-only">Unassign</span>
        `;
        container.appendChild(btn);
      }
    } else {
      agentDisplay.classList.add('hidden');
      agentSelect.classList.remove('hidden');
      saveBtn.classList.remove('hidden');
      saveBtn.textContent = 'Save';
    }
  }
  window.updateAgentAssignmentUI = updateAgentAssignmentUI;
  
  // Exported: switch to editing assignment
  window.editAgentAssignment = function(elementId) {
    const agentDisplay = document.getElementById(`agent-display-${elementId}`);
    const agentSelect = document.getElementById(`agent-select-${elementId}`);
    const saveBtn = document.getElementById(`save-btn-${elementId}`);
    if (!agentDisplay || !agentSelect || !saveBtn) return;
    
    // Get the currently displayed agent name to preserve selection
    const currentAgentSpan = agentDisplay.querySelector('span');
    const currentAgentName = currentAgentSpan ? currentAgentSpan.textContent.trim() : '';
    
    // Find and select the corresponding option in the dropdown
    if (currentAgentName) {
      const matchingOption = Array.from(agentSelect.options).find(option => 
        option.text.trim() === currentAgentName
      );
      if (matchingOption) {
        agentSelect.value = matchingOption.value;
      }
    }
    
    agentDisplay.classList.add('hidden');
    agentSelect.classList.remove('hidden');
    saveBtn.classList.remove('hidden');
    saveBtn.textContent = 'Save';
    agentSelect.focus();
  };
  
  // Exported: save assignment (used by both pages)
  window.saveAgentAssignment = async function(elementId, agentId, buttonElement) {
    const saveBtn = buttonElement || document.getElementById(`save-btn-${elementId}`);
    if (!saveBtn) {
      console.error('Save button not found');
      window.showToast && showToast('Error: Could not find save button', 'error');
      return;
    }
    const selectElement = document.getElementById(`agent-select-${elementId}`);
    if (!selectElement) {
      console.error('Select element not found');
      window.showToast && showToast('Error: Could not find select element', 'error');
      return;
    }
  
    const selectedAgentId = selectElement.value;
    if (!selectedAgentId) {
      window.showToast && showToast('Please select an agent', 'error');
      return;
    }
  
    saveBtn.disabled = true;
    saveBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Saving...';
  
    try {
      // Prefer header span if present (emi-payment page)
      let loanRefNo = (document.getElementById('selected-loan-ref')?.textContent || '').trim();
      // Fallback: get from row attributes (upcomingEMI page)
      if (!loanRefNo) {
        const row = saveBtn.closest('tr');
        loanRefNo = row?.getAttribute('data-loan-ref') || '';
      }
      if (!loanRefNo) throw new Error('Loan reference not found');
  
      // Find numeric schedule id from the row
      const row = saveBtn.closest('tr');
      const numericScheduleId = row?.getAttribute('data-id');
      if (!numericScheduleId) throw new Error('Schedule ID not found');
  
      const url = (window.EMI_PAYMENT_CONFIG && window.EMI_PAYMENT_CONFIG.assignAgentUrl) || '';
      if (!url) throw new Error('Assign Agent URL not configured');
  
      const resp = await fetch(url, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': getCookie('csrftoken') || ''
        },
        body: JSON.stringify({
          loan_ref_no: loanRefNo,
          schedule_id: numericScheduleId,
          agent_id: selectedAgentId
        })
      });
  
      if (!resp.ok) {
        const err = await resp.json().catch(() => ({}));
        throw new Error(err.detail || 'Failed to assign agent');
      }
  
      const result = await resp.json();
      window.showToast && showToast('Agent assigned successfully', 'success');
  
      const selectedOption = selectElement.options[selectElement.selectedIndex];
      const agentName = (result.assigned_agent_name || (selectedOption ? selectedOption.text : '')).trim();
      
      const keepVisible = !!(window.EMI_PAYMENT_CONFIG && window.EMI_PAYMENT_CONFIG.keepSelectVisible);
      if (keepVisible) {
        // Ensure select shows the saved agent, keep it visible, and hide Save until next change
        if (agentId && selectElement.value !== agentId) {
          selectElement.value = agentId;
        }
        // Mirror display text (kept hidden by template)
        const display = document.getElementById(`agent-display-${elementId}`);
        if (display) {
          const span = display.querySelector('span');
          if (span) span.textContent = agentName;
        }
        saveBtn.classList.add('hidden');
        // Also ensure the Unassign (trash) icon is present immediately
        const container = selectElement.parentElement;
        if (container && !container.querySelector(`button[data-unassign-for="${elementId}"]`)) {
          const numericEmiId = String(elementId).split('-').pop();
          const btn = document.createElement('button');
          btn.type = 'button';
          btn.title = 'Unassign agent';
          btn.setAttribute('data-unassign-for', elementId);
          btn.className = 'inline-flex items-center p-1 ml-0 rounded-md text-red-600 hover:text-red-700';
          btn.innerHTML = `
            <svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4" viewBox="0 0 24 24"
                 onclick="openUnassignPopover(${numericEmiId}, this)"
                 fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <polyline points="3 6 5 6 21 6" />
              <path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6" />
              <path d="M10 11v6" />
              <path d="M14 11v6" />
              <path d="M9 6V4a2 2 0 0 1 2-2h2a2 2 0 0 1 2 2v2" />
            </svg>
            <span class="sr-only">Unassign</span>
          `;
          container.appendChild(btn);
        }
      } else {
        updateAgentAssignmentUI(elementId, agentName);
      }
    } catch (e) {
      console.error('Error in saveAgentAssignment:', e);
      window.showToast && showToast(e.message || 'An error occurred while assigning agent', 'error');
    } finally {
      saveBtn.disabled = false;
      saveBtn.textContent = 'Save';
    }
  };