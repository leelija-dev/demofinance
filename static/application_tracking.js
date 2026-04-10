// Dynamic step configuration based on status
function getDynamicSteps(status, applicationData = null) {
    const isBranchCreated = applicationData && (!applicationData.agent || applicationData.created_by_branch);
    let baseSteps;
    if (isBranchCreated) {
        baseSteps = [
            {
                id: 'branch',
                name: 'Branch Submission',
                description: 'Application submitted by branch',
                status: 'completed',
                timestamp: applicationData?.submitted_at || null,
                category: 'branch',
                details: null
            }
        ];
    } else {
        baseSteps = [
            {
                id: 'agent',
                name: 'Agent Submission',
                description: 'Application submitted by agent',
                status: 'completed',
                timestamp: applicationData?.submitted_at || null,
                category: 'agent',
                details: null
            }
        ];
    }
    
    // Get status-specific description
    function getStatusDescription(status) {
        const descriptions = {
            'pending': isBranchCreated ? 'Application submitted by branch and pending HQ review' : 'Application submitted and pending review',
            'active': isBranchCreated ? 'Application is active and under HQ processing' : 'Application is active and under processing',
            'document_requested': isBranchCreated ? 'HQ has requested additional documents' : 'Branch has requested additional documents',
            'document_requested_by_hq': 'HQ has requested additional documents',
            'resubmitted': isBranchCreated ? 'Documents resubmitted by branch - awaiting HQ review' : 'Documents resubmitted - awaiting branch review',
            'branch_document_accepted': isBranchCreated ? 'Documents accepted by HQ - pending approval' : 'Documents accepted by branch - pending approval',
            'branch_approved': isBranchCreated ? 'Branch approved application - forwarded to headquarters' : 'Branch approved - forwarded to headquarters',
            'rejected_by_branch': isBranchCreated ? 'Application rejected by branch' : 'Application rejected by branch',
            'hq_approved': 'Application approved by headquarters',
            'hq_rejected': 'Application rejected by headquarters',
            'disbursed': 'Loan amount disbursed to customer',
            'disbursed_fund_released': 'Loan disbursed and funds released to customer',
            'success': 'Application successfully processed',
            'reject': 'Application rejected',
            'inactive': 'Application marked as inactive'
        };
        return descriptions[status] || (isBranchCreated ? 'Application under HQ review' : 'Application under review');
    }
    
    // Build complete history from application data
    function buildCompleteHistory(applicationData) {
        const history = [];
        // Add submission
        if (applicationData?.submitted_at) {
            history.push({
                id: isBranchCreated ? 'branch_submission' : 'agent_submission',
                name: isBranchCreated ? 'Branch Submission' : 'Agent Submission',
                description: isBranchCreated ? 'Application submitted by branch' : 'Application submitted by agent',
                status: 'completed',
                timestamp: applicationData.submitted_at,
                category: isBranchCreated ? 'branch' : 'agent',
                details: isBranchCreated ? {
                    branch: applicationData.branch_name || applicationData.branch || '',
                    submitted_at: applicationData.submitted_at
                } : {
                    agent: applicationData.agent?.full_name,
                    submitted_at: applicationData.submitted_at
                }
            });
        }
        // Add HQ document requests (for branch-created)
        if (isBranchCreated && applicationData?.document_requests) {
            applicationData.document_requests.forEach((request, index) => {
                const requestStatus = request.is_resolved ? 'completed' : 'current';
                const category = 'hq';
                history.push({
                    id: `hq_document_request_${index}`,
                    name: 'HQ Document Request',
                    description: `${request.document_type.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase())} requested - ${request.reason.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase())}`,
                    status: requestStatus,
                    timestamp: request.requested_at,
                    category: category,
                    details: {
                        document_type: request.document_type,
                        reason: request.reason,
                        comment: request.comment,
                        requested_by: request.requested_by || request.requested_by_hq,
                        requested_at: request.requested_at,
                        is_resolved: request.is_resolved,
                        resolved_at: request.resolved_at
                    }
                });
            });
        } else if (applicationData?.document_requests) {
            // Agent-created: keep original logic
            applicationData.document_requests.forEach((request, index) => {
                const requestStatus = request.is_resolved ? 'completed' : 'current';
                const category = request.category || (request.requested_by_hq ? 'hq' : 'branch');
                history.push({
                    id: `document_request_${index}`,
                    name: (category === 'branch') ? 'Branch Document Request' : 'HQ Document Request',
                    description: `${request.document_type.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase())} requested - ${request.reason.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase())}`,
                    status: requestStatus,
                    timestamp: request.requested_at,
                    category: category,
                    details: {
                        document_type: request.document_type,
                        reason: request.reason,
                        comment: request.comment,
                        requested_by: request.requested_by || request.requested_by_hq,
                        requested_at: request.requested_at,
                        is_resolved: request.is_resolved,
                        resolved_at: request.resolved_at
                    }
                });
            });
        }
        // Add branch resubmission (for branch-created)
        if (isBranchCreated && applicationData?.document_reuploads) {
            applicationData.document_reuploads.forEach((reupload, index) => {
                history.push({
                    id: `branch_resubmission_${index}`,
                    name: 'Branch Re-uploaded',
                    description: `${reupload.document_type.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase())} re-uploaded`,
                    status: 'completed',
                    timestamp: reupload.uploaded_at,
                    category: 'branch',
                    details: {
                        document_type: reupload.document_type,
                        agent_note: reupload.agent_note,
                        uploaded_by: reupload.uploaded_by,
                        uploaded_at: reupload.uploaded_at
                    }
                });
            });
        } else if (applicationData?.document_reuploads) {
            // Agent-created: keep original logic
            applicationData.document_reuploads.forEach((reupload, index) => {
                history.push({
                    id: `document_reupload_${index}`,
                    name: 'Document Reupload',
                    description: `${reupload.document_type.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase())} reuploaded`,
                    status: 'completed',
                    timestamp: reupload.uploaded_at,
                    category: 'agent',
                    details: {
                        document_type: reupload.document_type,
                        agent_note: reupload.agent_note,
                        uploaded_by: reupload.uploaded_by,
                        uploaded_at: reupload.uploaded_at
                    }
                });
            });
        }
        // Add HQ document reviews (for branch-created)
        if (isBranchCreated && applicationData?.document_reviews) {
            applicationData.document_reviews.forEach((review, index) => {
                const reviewStatus = review.decision === 'approved' ? 'completed' : 
                                   review.decision === 'rejected' || review.decision === 'request_again' ? 'failed' : 'current';
                history.push({
                    id: `hq_document_review_${index}`,
                    name: 'HQ Document Review',
                    description: `${review.document_type ? review.document_type.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase()) + ' - ' : ''}${review.decision.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase())}`,
                    status: reviewStatus,
                    timestamp: review.reviewed_at,
                    category: 'hq',
                    details: {
                        document_type: review.document_type,
                        decision: review.decision,
                        review_comment: review.review_comment,
                        reviewed_by: review.reviewed_by,
                        reviewed_at: review.reviewed_at
                    }
                });
            });
        } else if (applicationData?.document_reviews) {
            // Agent-created: keep original logic
            applicationData.document_reviews.forEach((review, index) => {
                const reviewStatus = review.decision === 'approved' ? 'completed' : 
                                   review.decision === 'rejected' || review.decision === 'request_again' ? 'failed' : 'current';
                history.push({
                    id: `standalone_review_${index}`,
                    name: 'Document Review',
                    description: `${review.document_type ? review.document_type.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase()) + ' - ' : ''}${review.decision.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase())}`,
                    status: reviewStatus,
                    timestamp: review.reviewed_at,
                    category: 'branch',
                    details: {
                        document_type: review.document_type,
                        decision: review.decision,
                        review_comment: review.review_comment,
                        reviewed_by: review.reviewed_by,
                        reviewed_at: review.reviewed_at
                    }
                });
            });
        }
        // Add branch approval (for branch-created) - check historical indicators
        const shouldShowBranchApproval = isBranchCreated ? 
            (applicationData?.status === 'branch_approved' || 
             applicationData?.ever_branch_approved || 
             ['hq_approved', 'hq_rejected', 'disbursed', 'disbursed_fund_released'].includes(applicationData?.status)) :
            (applicationData?.status === 'branch_approved' || 
             applicationData?.ever_branch_approved || 
             ['hq_approved', 'hq_rejected', 'disbursed', 'disbursed_fund_released'].includes(applicationData?.status));
        
        if (shouldShowBranchApproval) {
            history.push({
                id: 'branch_approval',
                name: 'Branch Approval',
                description: 'Application approved by branch',
                status: 'completed',
                timestamp: applicationData.branch_approved_at || applicationData.approved_at || applicationData.updated_at || applicationData.submitted_at,
                category: 'branch',
                details: {
                    action: 'approved',
                    status: applicationData.status,
                    approved_by: applicationData.branch_approver || null
                }
            });
        }
        
        // Add HQ approval/rejection - check historical indicators
        const shouldShowHQApproval = applicationData?.status === 'hq_approved' || 
                                   applicationData?.hq_approved_at || 
                                   ['disbursed', 'disbursed_fund_released'].includes(applicationData?.status);
        
        if (shouldShowHQApproval) {
            history.push({
                id: 'hq_approval',
                name: 'HQ Approval',
                description: 'Application approved by headquarters',
                status: 'completed',
                timestamp: applicationData.hq_approved_at || applicationData.approved_at || applicationData.updated_at || applicationData.submitted_at,
                category: 'hq',
                details: {
                    action: 'approved',
                    status: applicationData.status,
                    approved_by: applicationData.hq_approver || null
                }
            });
        } else if (applicationData?.status === 'hq_rejected') {
            history.push({
                id: 'hq_rejection',
                name: 'HQ Rejection',
                description: 'Application rejected by headquarters',
                status: 'failed',
                timestamp: applicationData.submitted_at,
                category: 'hq',
                details: {
                    action: 'rejected',
                    status: applicationData.status
                }
            });
        }
        // Add disbursement status - check historical indicators
        const shouldShowDisbursement = applicationData?.status === 'disbursed' || 
                                     applicationData?.disbursed_at || 
                                     applicationData?.status === 'disbursed_fund_released';
        
        if (shouldShowDisbursement) {
            history.push({
                id: 'loan_disbursed',
                name: 'Loan Disbursed',
                description: 'Loan amount disbursed to customer',
                status: 'completed',
                timestamp: applicationData.disbursed_at || applicationData.updated_at || applicationData.submitted_at,
                category: 'system',
                details: {
                    action: 'disbursed',
                    status: applicationData.status,
                    disbursed_at: applicationData.disbursed_at
                }
            });
        }
        
        // Add disbursed fund released status - check historical indicators
        const shouldShowFundRelease = applicationData?.status === 'disbursed_fund_released' || 
                                    applicationData?.disbursed_at; // If disbursed_at exists, fund release is likely to have happened
        
        if (shouldShowFundRelease) {
            history.push({
                id: 'fund_released',
                name: 'Fund Released',
                description: 'Loan disbursed and funds released to customer',
                status: 'completed',
                timestamp: applicationData.disbursed_at || applicationData.updated_at || applicationData.submitted_at,
                category: 'system',
                details: {
                    action: 'fund released',
                    status: applicationData.status,
                    disbursed_at: applicationData.disbursed_at
                }
            });
        }
        // Rejected/inactive
        if (applicationData?.status === 'reject' || applicationData?.status === 'inactive') {
            history.push({
                id: 'application_rejected',
                name: 'Application Rejected',
                description: 'Application rejected or inactive',
                status: 'failed',
                timestamp: applicationData.updated_at || applicationData.submitted_at,
                category: 'system',
                details: {
                    action: 'rejected',
                    status: applicationData.status
                }
            });
        }
        return history;
    }
    // Define status progression and their corresponding steps
    if (isBranchCreated) {
        const statusFlow = {
            'pending': {
                steps: baseSteps,
                currentStep: 'branch',
                history: applicationData ? buildCompleteHistory(applicationData) : []
            },
            'active': {
                steps: baseSteps,
                currentStep: 'branch',
                history: applicationData ? buildCompleteHistory(applicationData) : []
            },
            'document_requested_by_hq': {
                steps: [
                    ...baseSteps,
                    {
                        id: 'hq_document_request',
                        name: 'HQ Document Request',
                        description: getStatusDescription('document_requested_by_hq'),
                        status: 'current',
                        timestamp: null,
                        category: 'hq',
                        details: null
                    }
                ],
                currentStep: 'hq_document_request',
                history: applicationData ? buildCompleteHistory(applicationData) : []
            },
            'resubmitted': {
                steps: [
                    ...baseSteps,
                    {
                        id: 'branch_resubmission',
                        name: 'Branch Re-uploaded',
                        description: getStatusDescription('resubmitted'),
                        status: 'current',
                        timestamp: null,
                        category: 'branch',
                        details: null
                    }
                ],
                currentStep: 'branch_resubmission',
                history: applicationData ? buildCompleteHistory(applicationData) : []
            },
            'branch_approved': {
                steps: [
                    ...baseSteps,
                    {
                        id: 'branch_approval',
                        name: 'Branch Approval',
                        description: getStatusDescription('branch_approved'),
                        status: 'completed',
                        timestamp: null,
                        category: 'branch',
                        details: null
                    },
                    {
                        id: 'hq_review',
                        name: 'HQ Review',
                        description: 'HQ reviewing application',
                        status: 'current',
                        timestamp: null,
                        category: 'hq',
                        details: null
                    }
                ],
                currentStep: 'hq_review',
                history: applicationData ? buildCompleteHistory(applicationData) : []
            },
            'hq_approved': {
                steps: [
                    ...baseSteps,
                    {
                        id: 'branch_approval',
                        name: 'Branch Approval',
                        description: getStatusDescription('branch_approved'),
                        status: 'completed',
                        timestamp: null,
                        category: 'branch',
                        details: null
                    },
                    {
                        id: 'hq_approval',
                        name: 'HQ Approval',
                        description: getStatusDescription('hq_approved'),
                        status: 'completed',
                        timestamp: null,
                        category: 'hq',
                        details: null
                    },
                    {
                        id: 'disbursement',
                        name: 'Disbursement',
                        description: 'Loan disbursement in progress',
                        status: 'current',
                        timestamp: null,
                        category: 'system',
                        details: null
                    }
                ],
                currentStep: 'disbursement',
                history: applicationData ? buildCompleteHistory(applicationData) : []
            },
            'disbursed': {
                steps: [
                    ...baseSteps,
                    {
                        id: 'branch_approval',
                        name: 'Branch Approval',
                        description: getStatusDescription('branch_approved'),
                        status: 'completed',
                        timestamp: null,
                        category: 'branch',
                        details: null
                    },
                    {
                        id: 'hq_approval',
                        name: 'HQ Approval',
                        description: getStatusDescription('hq_approved'),
                        status: 'completed',
                        timestamp: null,
                        category: 'hq',
                        details: null
                    },
                    {
                        id: 'disbursement',
                        name: 'Loan Disbursed',
                        description: getStatusDescription('disbursed'),
                        status: 'completed',
                        timestamp: null,
                        category: 'system',
                        details: null
                    },
                    {
                        id: 'fund_release',
                        name: 'Fund Release',
                        description: 'Fund release in progress',
                        status: 'current',
                        timestamp: null,
                        category: 'system',
                        details: null
                    }
                ],
                currentStep: 'fund_release',
                history: applicationData ? buildCompleteHistory(applicationData) : []
            },
            'disbursed_fund_released': {
                steps: [
                    ...baseSteps,
                    {
                        id: 'branch_approval',
                        name: 'Branch Approval',
                        description: getStatusDescription('branch_approved'),
                        status: 'completed',
                        timestamp: null,
                        category: 'branch',
                        details: null
                    },
                    {
                        id: 'hq_approval',
                        name: 'HQ Approval',
                        description: getStatusDescription('hq_approved'),
                        status: 'completed',
                        timestamp: null,
                        category: 'hq',
                        details: null
                    },
                    {
                        id: 'disbursement',
                        name: 'Loan Disbursed',
                        description: getStatusDescription('disbursed'),
                        status: 'completed',
                        timestamp: null,
                        category: 'system',
                        details: null
                    },
                    {
                        id: 'fund_release',
                        name: 'Fund Released',
                        description: getStatusDescription('disbursed_fund_released'),
                        status: 'completed',
                        timestamp: null,
                        category: 'system',
                        details: null
                    }
                ],
                currentStep: 'fund_release',
                history: applicationData ? buildCompleteHistory(applicationData) : []
            },
            'hq_rejected': {
                steps: [
                    ...baseSteps,
                    {
                        id: 'branch_approval',
                        name: 'Branch Approval',
                        description: getStatusDescription('branch_approved'),
                        status: 'completed',
                        timestamp: null,
                        category: 'branch',
                        details: null
                    },
                    {
                        id: 'hq_rejection',
                        name: 'HQ Rejection',
                        description: getStatusDescription('hq_rejected'),
                        status: 'current',
                        timestamp: null,
                        category: 'hq',
                        details: null
                    }
                ],
                currentStep: 'hq_rejection',
                history: applicationData ? buildCompleteHistory(applicationData) : []
            },
            'success': {
                steps: [
                    ...baseSteps,
                    {
                        id: 'branch_approval',
                        name: 'Branch Approval',
                        description: getStatusDescription('branch_approved'),
                        status: 'completed',
                        timestamp: null,
                        category: 'branch',
                        details: null
                    },
                    {
                        id: 'hq_approval',
                        name: 'HQ Approval',
                        description: getStatusDescription('hq_approved'),
                        status: 'completed',
                        timestamp: null,
                        category: 'hq',
                        details: null
                    },
                    {
                        id: 'disbursement',
                        name: 'Loan Disbursed',
                        description: getStatusDescription('disbursed'),
                        status: 'completed',
                        timestamp: null,
                        category: 'system',
                        details: null
                    },
                    {
                        id: 'fund_release',
                        name: 'Fund Released',
                        description: getStatusDescription('disbursed_fund_released'),
                        status: 'completed',
                        timestamp: null,
                        category: 'system',
                        details: null
                    }
                ],
                currentStep: 'fund_release',
                history: applicationData ? buildCompleteHistory(applicationData) : []
            },
            'reject': {
                steps: [
                    ...baseSteps,
                    {
                        id: 'application_rejected',
                        name: 'Application Rejected',
                        description: getStatusDescription('reject'),
                        status: 'failed',
                        timestamp: null,
                        category: 'system',
                        details: null
                    }
                ],
                currentStep: 'application_rejected',
                history: applicationData ? buildCompleteHistory(applicationData) : []
            },
            'inactive': {
                steps: [
                    ...baseSteps,
                    {
                        id: 'application_inactive',
                        name: 'Application Inactive',
                        description: getStatusDescription('inactive'),
                        status: 'failed',
                        timestamp: null,
                        category: 'system',
                        details: null
                    }
                ],
                currentStep: 'application_inactive',
                history: applicationData ? buildCompleteHistory(applicationData) : []
            }
        };
        return statusFlow[status] || statusFlow['pending'];
    }
    // Agent-created and default: keep original statusFlow logic
    const statusFlow = {
        'pending': {
            steps: baseSteps,
            currentStep: 'agent',
            history: applicationData ? buildCompleteHistory(applicationData) : []
        },
        'active': {
            steps: baseSteps,
            currentStep: 'agent',
            history: applicationData ? buildCompleteHistory(applicationData) : []
        },
        'document_requested': {
            steps: [
                ...baseSteps,
                {
                    id: 'branch_review',
                    name: 'Branch Review',
                    description: getStatusDescription('document_requested'),
                    status: 'current',
                    timestamp: null,
                    category: 'branch',
                    details: null
                }
            ],
            currentStep: 'branch_review',
            history: applicationData ? buildCompleteHistory(applicationData) : []
        },
        'resubmitted': {
            steps: [
                ...baseSteps,
                {
                    id: 'branch_review',
                    name: 'Branch Review',
                    description: getStatusDescription('resubmitted'),
                    status: 'current',
                    timestamp: null,
                    category: 'branch',
                    details: null
                }
            ],
            currentStep: 'branch_review',
            history: applicationData ? buildCompleteHistory(applicationData) : []
        },
        'branch_document_accepted': {
            steps: [
                ...baseSteps,
                {
                    id: 'branch_review',
                    name: 'Branch Review',
                    description: 'Documents accepted by branch',
                    status: 'completed',
                    timestamp: null,
                    category: 'branch',
                    details: null
                },
                {
                    id: 'branch_approval',
                    name: 'Branch Approval',
                    description: getStatusDescription('branch_document_accepted'),
                    status: 'current',
                    timestamp: null,
                    category: 'branch',
                    details: null
                }
            ],
            currentStep: 'branch_approval',
            history: applicationData ? buildCompleteHistory(applicationData) : []
        },
        'branch_approved': {
            steps: [
                ...baseSteps,
                {
                    id: 'branch_review',
                    name: 'Branch Review',
                    description: 'Branch review completed',
                    status: 'completed',
                    timestamp: null,
                    category: 'branch',
                    details: null
                },
                {
                    id: 'branch_approval',
                    name: 'Branch Approval',
                    description: 'Branch approved - Pending HQ approval',
                    status: 'completed',
                    timestamp: null,
                    category: 'branch',
                    details: null
                },
                {
                    id: 'hq_review',
                    name: 'Headquarter Review',
                    description: 'HQ reviewing application',
                    status: 'current',
                    timestamp: null,
                    category: 'hq',
                    details: null
                }
            ],
            currentStep: 'hq_review',
            history: applicationData ? buildCompleteHistory(applicationData) : []
        },
        'rejected_by_branch': {
            steps: [
                ...baseSteps,
                {
                    id: 'branch_review',
                    name: 'Branch Review',
                    description: getStatusDescription('rejected_by_branch'),
                    status: 'failed',
                    timestamp: null,
                    category: 'branch',
                    details: null
                }
            ],
            currentStep: 'branch_review',
            history: applicationData ? buildCompleteHistory(applicationData) : []
        },
        'document_requested_by_hq': {
            steps: [
                ...baseSteps,
                {
                    id: 'branch_review',
                    name: 'Branch Review',
                    description: 'Branch review completed',
                    status: 'completed',
                    timestamp: null,
                    category: 'branch',
                    details: null
                },
                {
                    id: 'branch_approval',
                    name: 'Branch Approval',
                    description: 'Branch approved',
                    status: 'completed',
                    timestamp: null,
                    category: 'branch',
                    details: null
                },
                {
                    id: 'hq_review',
                    name: 'Headquarter Review',
                    description: getStatusDescription('document_requested_by_hq'),
                    status: 'current',
                    timestamp: null,
                    category: 'hq',
                    details: null
                }
            ],
            currentStep: 'hq_review',
            history: applicationData ? buildCompleteHistory(applicationData) : []
        },
        'hq_approved': {
            steps: [
                ...baseSteps,
                {
                    id: 'branch_review',
                    name: 'Branch Review',
                    description: 'Branch review completed',
                    status: 'completed',
                    timestamp: null,
                    category: 'branch',
                    details: null
                },
                {
                    id: 'branch_approval',
                    name: 'Branch Approval',
                    description: 'Branch approved',
                    status: 'completed',
                    timestamp: null,
                    category: 'branch',
                    details: null
                },
                {
                    id: 'hq_review',
                    name: 'Headquarter Review',
                    description: 'HQ approved',
                    status: 'completed',
                    timestamp: null,
                    category: 'hq',
                    details: null
                },
                {
                    id: 'disbursement',
                    name: 'Disbursement',
                    description: 'Loan disbursement in progress',
                    status: 'current',
                    timestamp: null,
                    category: 'system',
                    details: null
                }
            ],
            currentStep: 'disbursement',
            history: applicationData ? buildCompleteHistory(applicationData) : []
        },
        'disbursed': {
            steps: [
                ...baseSteps,
                {
                    id: 'branch_review',
                    name: 'Branch Review',
                    description: 'Branch review completed',
                    status: 'completed',
                    timestamp: null,
                    category: 'branch',
                    details: null
                },
                {
                    id: 'branch_approval',
                    name: 'Branch Approval',
                    description: 'Branch approved',
                    status: 'completed',
                    timestamp: null,
                    category: 'branch',
                    details: null
                },
                {
                    id: 'hq_review',
                    name: 'Headquarter Review',
                    description: 'HQ approved',
                    status: 'completed',
                    timestamp: null,
                    category: 'hq',
                    details: null
                },
                {
                    id: 'disbursement',
                    name: 'Loan Disbursed',
                    description: getStatusDescription('disbursed'),
                    status: 'completed',
                    timestamp: null,
                    category: 'system',
                    details: null
                },
                {
                    id: 'fund_release',
                    name: 'Fund Release',
                    description: 'Fund release in progress',
                    status: 'current',
                    timestamp: null,
                    category: 'system',
                    details: null
                }
            ],
            currentStep: 'fund_release',
            history: applicationData ? buildCompleteHistory(applicationData) : []
        },
        'disbursed_fund_released': {
            steps: [
                ...baseSteps,
                {
                    id: 'branch_review',
                    name: 'Branch Review',
                    description: 'Branch review completed',
                    status: 'completed',
                    timestamp: null,
                    category: 'branch',
                    details: null
                },
                {
                    id: 'branch_approval',
                    name: 'Branch Approval',
                    description: 'Branch approved',
                    status: 'completed',
                    timestamp: null,
                    category: 'branch',
                    details: null
                },
                {
                    id: 'hq_review',
                    name: 'Headquarter Review',
                    description: 'HQ approved',
                    status: 'completed',
                    timestamp: null,
                    category: 'hq',
                    details: null
                },
                {
                    id: 'disbursement',
                    name: 'Loan Disbursed',
                    description: getStatusDescription('disbursed'),
                    status: 'completed',
                    timestamp: null,
                    category: 'system',
                    details: null
                },
                {
                    id: 'fund_release',
                    name: 'Fund Released',
                    description: getStatusDescription('disbursed_fund_released'),
                    status: 'completed',
                    timestamp: null,
                    category: 'system',
                    details: null
                }
            ],
            currentStep: 'fund_release',
            history: applicationData ? buildCompleteHistory(applicationData) : []
        },
        'hq_rejected': {
            steps: [
                ...baseSteps,
                {
                    id: 'branch_review',
                    name: 'Branch Review',
                    description: 'Branch review completed',
                    status: 'completed',
                    timestamp: null,
                    category: 'branch',
                    details: null
                },
                {
                    id: 'branch_approval',
                    name: 'Branch Approval',
                    description: 'Branch approved',
                    status: 'completed',
                    timestamp: null,
                    category: 'branch',
                    details: null
                },
                {
                    id: 'hq_review',
                    name: 'Headquarter Review',
                    description: getStatusDescription('hq_rejected'),
                    status: 'failed',
                    timestamp: null,
                    category: 'hq',
                    details: null
                }
            ],
            currentStep: 'hq_review',
            history: applicationData ? buildCompleteHistory(applicationData) : []
        },
        'success': {
            steps: [
                ...baseSteps,
                {
                    id: 'branch_review',
                    name: 'Branch Review',
                    description: 'Branch review completed',
                    status: 'completed',
                    timestamp: null,
                    category: 'branch',
                    details: null
                },
                {
                    id: 'branch_approval',
                    name: 'Branch Approval',
                    description: 'Branch approved',
                    status: 'completed',
                    timestamp: null,
                    category: 'branch',
                    details: null
                },
                {
                    id: 'hq_review',
                    name: 'Headquarter Review',
                    description: 'HQ approved',
                    status: 'completed',
                    timestamp: null,
                    category: 'hq',
                    details: null
                },
                {
                    id: 'disbursement',
                    name: 'Loan Disbursed',
                    description: getStatusDescription('disbursed'),
                    status: 'completed',
                    timestamp: null,
                    category: 'system',
                    details: null
                },
                {
                    id: 'fund_release',
                    name: 'Fund Released',
                    description: getStatusDescription('disbursed_fund_released'),
                    status: 'completed',
                    timestamp: null,
                    category: 'system',
                    details: null
                }
            ],
            currentStep: 'fund_release',
            history: applicationData ? buildCompleteHistory(applicationData) : []
        },
        'reject': {
            steps: [
                ...baseSteps,
                {
                    id: 'application_rejected',
                    name: 'Application Rejected',
                    description: getStatusDescription('reject'),
                    status: 'failed',
                    timestamp: null,
                    category: 'system',
                    details: null
                }
            ],
            currentStep: 'application_rejected',
            history: applicationData ? buildCompleteHistory(applicationData) : []
        },
        'inactive': {
            steps: [
                ...baseSteps,
                {
                    id: 'application_inactive',
                    name: 'Application Inactive',
                    description: getStatusDescription('inactive'),
                    status: 'failed',
                    timestamp: null,
                    category: 'system',
                    details: null
                }
            ],
            currentStep: 'application_inactive',
            history: applicationData ? buildCompleteHistory(applicationData) : []
        }
    };
    return statusFlow[status] || statusFlow['pending'];
}

function updateDynamicTrackingStatus(status, submittedAt, applicationData = null) {
    const { steps, currentStep, history } = getDynamicSteps(status, applicationData);
    
    // Clear existing tracking UI
    const trackingContainer = document.getElementById('customTrackingBtn');
    if (trackingContainer) {
        trackingContainer.innerHTML = '';
    }
    
    // Get status color
    function getStatusColor(status) {
        const colors = {
            'pending': 'orange',
            'active': 'blue',
            'document_requested': 'red',
            'resubmitted': 'blue',
            'branch_document_accepted': 'green',
            'branch_approved': 'green',
            'rejected_by_branch': 'red',
            'document_requested_by_hq': 'red',
            'hq_approved': 'green',
            'hq_rejected': 'red',
            'disbursed': 'green',
            'disbursed_fund_released': 'green',
            'success': 'green',
            'reject': 'red',
            'inactive': 'gray'
        };
        return colors[status] || 'gray';
    }
    
    // Build dynamic tracking UI
    let trackingHTML = '';
    steps.forEach((step, index) => {
        const isCurrent = step.id === currentStep;
        const isCompleted = step.status === 'completed';
        const isFailed = step.status === 'failed';
        
        let stepClass = 'w-6 h-6 flex items-center justify-center rounded-full font-bold';
        let textClass = 'mt-2 text-sm font-medium';
        
        if (isCompleted) {
            stepClass += ' bg-success-500 text-white';
            textClass += ' text-success-600';
        } else if (isFailed) {
            stepClass += ' bg-error-500 text-white';
            textClass += ' text-error-600';
        } else if (isCurrent) {
            const statusColor = getStatusColor(status);
            if (statusColor === 'red') {
                stepClass += ' bg-error-500 text-white';
                textClass += ' text-error-600';
            } else if (statusColor === 'green') {
                stepClass += ' bg-success-500 text-white';
                textClass += ' text-success-600';
            } else if (statusColor === 'orange') {
                stepClass += ' bg-orange-500 text-white';
                textClass += ' text-orange-600';
            } else {
                stepClass += ' bg-brand-500 text-white';
                textClass += ' text-brand-600';
            }
        } else {
            stepClass += ' bg-gray-300 text-gray-700';
            textClass += ' text-gray-500';
        }
        
        trackingHTML += `
            <div class="flex w-auto flex-col items-center flex-1">
                <div class="${stepClass}">${index + 1}</div>
                <span class="${textClass}">${step.name}</span>
            </div>
        `;
        
        // Add connector line (except for last step)
        if (index < steps.length - 1) {
            const nextStep = steps[index + 1];
            const isNextCompleted = nextStep.status === 'completed';
            const isNextCurrent = nextStep.id === currentStep;
            
            let connectorClass = 'flex-1 h-1';
            if (isCompleted || (isNextCompleted || isNextCurrent)) {
                const statusColor = getStatusColor(status);
                if (statusColor === 'red') {
                    connectorClass += ' bg-error-500';
                } else if (statusColor === 'green') {
                    connectorClass += ' bg-success-500';
                } else if (statusColor === 'orange') {
                    connectorClass += ' bg-orange-500';
                } else {
                    connectorClass += ' bg-brand-500';
                }
            } else {
                connectorClass += ' bg-gray-300';
            }
            
            trackingHTML += `<div class="${connectorClass}"></div>`;
        }
    });
    
    if (trackingContainer) {
        trackingContainer.innerHTML = trackingHTML;
    }
    
    // Update modal content with complete history
    updateDynamicStepHistory(steps, submittedAt, history);
}

// Format date time in IST
function formatDateTimeIST(dateInput) {
    if (!dateInput) return '';
    
    try {
        const date = new Date(dateInput);
        if (isNaN(date.getTime())) return '';
        
        // Format to IST (UTC+5:30)
        const istOptions = {
            year: 'numeric',
            month: '2-digit',
            day: '2-digit',
            hour: '2-digit',
            minute: '2-digit',
            second: '2-digit',
            timeZone: 'Asia/Kolkata'
        };
        
        return date.toLocaleString('en-IN', istOptions);
    } catch (error) {
        console.error('Error formatting date:', error);
        return '';
    }
}

function updateDynamicStepHistory(steps, submittedAt, history = []) {
    // Clear all history containers
    const historyContainers = ['history-agent', 'history-branch', 'history-hq', 'history-system'];
    historyContainers.forEach(containerId => {
        const container = document.getElementById(containerId);
        if (container) container.innerHTML = '';
    });
    
    // Sort history by timestamp (oldest first)
    const sortedHistory = [...history].sort((a, b) => {
        if (!a.timestamp && !b.timestamp) return 0;
        if (!a.timestamp) return 1;
        if (!b.timestamp) return -1;
        return new Date(a.timestamp) - new Date(b.timestamp);
    });
    
    // Group history by category
    const historyByCategory = {};
    sortedHistory.forEach(item => {
        if (!historyByCategory[item.category]) {
            historyByCategory[item.category] = [];
        }
        historyByCategory[item.category].push(item);
    });
    
    // Category configuration
    const categoryConfig = {
        'agent': {
            name: 'Agent Actions',
            icon: 'M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z',
            color: 'text-blue-600',
            bgColor: 'bg-blue-50',
            borderColor: 'border-blue-200'
        },
        'branch': {
            name: 'Branch Actions',
            icon: 'M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16m14 0h2m-2 0h-5m-9 0H3m2 0h5M9 7h1m-1 4h1m4-4h1m-1 4h1m-5 10v-5a1 1 0 011-1h2a1 1 0 011 1v5m-4 0h4',
            color: 'text-green-600',
            bgColor: 'bg-green-50',
            borderColor: 'border-green-200'
        },
        'hq': {
            name: 'Headquarters Actions',
            icon: 'M21 13.255A23.931 23.931 0 0112 15c-3.183 0-6.22-.62-9-1.745M16 6V4a2 2 0 00-2-2h-4a2 2 0 00-2-2v2m8 0V6a2 2 0 012 2v6a2 2 0 01-2 2H8a2 2 0 01-2-2V8a2 2 0 012-2V6',
            color: 'text-purple-600',
            bgColor: 'bg-purple-50',
            borderColor: 'border-purple-200'
        },
        'system': {
            name: 'System Actions',
            icon: 'M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z',
            color: 'text-gray-600',
            bgColor: 'bg-gray-50',
            borderColor: 'border-gray-200'
        }
    };
    
    // Render history for each category
    Object.keys(historyByCategory).forEach(category => {
        const containerId = `history-${category}`;
        const container = document.getElementById(containerId);
        if (!container) return;
        
        const config = categoryConfig[category] || categoryConfig['system'];
        
        let categoryHTML = `
            <div class="mb-4 p-4 ${config.bgColor} ${config.borderColor} rounded-lg">
                <div class="flex items-center mb-3">
                    <svg class="w-5 h-5 mr-2 ${config.color} dark:text-white/90" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="${config.icon}"></path>
                    </svg>
                    <h6 class="text-sm font-semibold ${config.color} dark:text-white/90">${config.name}</h6>
                    <span class="ml-auto text-xs text-gray-500">${historyByCategory[category].length} action(s)</span>
                </div>
        `;
        
        historyByCategory[category].forEach((item, index) => {
            const statusClass = item.status === 'completed' ? 'text-success-600' : 
                               item.status === 'current' ? 'text-brand-500' : 
                               item.status === 'failed' ? 'text-error-600' : 'text-gray-400';
            
            const statusText = item.status === 'completed' ? '✓ Completed' :
                              item.status === 'current' ? '● In Progress' : 
                              item.status === 'failed' ? '✗ Failed' : '○ Pending';
            
            const iconClass = item.status === 'completed' ? 'bg-success-500' : 
                             item.status === 'current' ? 'bg-brand-100' : 
                             item.status === 'failed' ? 'bg-error-100' : 'bg-gray-100';
            
            const iconTextClass = item.status === 'completed' ? 'text-success-500' : 
                                 item.status === 'current' ? 'text-brand-600' : 
                                 item.status === 'failed' ? 'text-error-600' : 'text-gray-400';
            
            // Build details section
            let detailsHTML = '';
            if (item.details) {
                detailsHTML += '<div class="mt-2 p-2 bg-white rounded border-l-4 border-gray-300">';
                
                if (item.details.agent_note) {
                    detailsHTML += `<p class="text-xs text-gray-600 mb-1"><strong>Agent Note:</strong> ${item.details.agent_note}</p>`;
                }
                if (item.details.review_comment) {
                    detailsHTML += `<p class="text-xs text-gray-600 mb-1"><strong>Review Comment:</strong> ${item.details.review_comment}</p>`;
                }
                if (item.details.uploaded_by) {
                    detailsHTML += `<p class="text-xs text-gray-600 mb-1"><strong>Uploaded by:</strong> ${item.details.uploaded_by}</p>`;
                }
                if (item.details.reviewed_by) {
                    detailsHTML += `<p class="text-xs text-gray-600 mb-1"><strong>Reviewed by:</strong> ${item.details.reviewed_by}</p>`;
                }
                if (item.details.requested_by) {
                    detailsHTML += `<p class="text-xs text-gray-600 mb-1"><strong>Requested by:</strong> ${item.details.requested_by}</p>`;
                }
                if (item.details.document_type) {
                    detailsHTML += `<p class="text-xs text-gray-600 mb-1"><strong>Document:</strong> ${item.details.document_type.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase())}</p>`;
                }
                if (item.details.reason) {
                    detailsHTML += `<p class="text-xs text-gray-600 mb-1"><strong>Reason:</strong> ${item.details.reason.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase())}</p>`;
                }
                if (item.details.comment) {
                    detailsHTML += `<p class="text-xs text-gray-600 mb-1"><strong>Comment:</strong> ${item.details.comment}</p>`;
                }
                if (item.details.decision) {
                    const decisionColor = item.details.decision === 'approved' ? 'text-green-600' : 
                                        item.details.decision === 'rejected' ? 'text-red-600' : 'text-yellow-600';
                    detailsHTML += `<p class="text-xs ${decisionColor} mb-1"><strong>Decision:</strong> ${item.details.decision.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase())}</p>`;
                }
                if (item.details.is_resolved !== undefined) {
                    const resolvedStatus = item.details.is_resolved ? 'text-green-600' : 'text-yellow-600';
                    const resolvedText = item.details.is_resolved ? 'Resolved' : 'Pending';
                    detailsHTML += `<p class="text-xs ${resolvedStatus} mb-1"><strong>Status:</strong> ${resolvedText}</p>`;
                }
                if (item.details.action === 'approved') {
                    const actionColor = item.details.action === 'approved' ? 'text-green-600' : 'text-red-600';
                    detailsHTML += `<p class="text-xs ${actionColor} mb-1"><strong>Action:</strong> ${item.details.action.replace(/\b\w/g, l => l.toUpperCase())}</p>`;
                }
                if (item.details.action === 'disbursed and released') {
                    const statusColor = item.details.action === 'disbursed and released' ? 'text-green-600' : 'text-red-600';
                    detailsHTML += `<p class="text-xs ${statusColor} mb-1"><strong>Action:</strong> ${item.details.action.replace(/\b\w/g, l => l.toUpperCase())}</p>`;
                }
                if (item.details.action === 'disbursed') {
                    const statusColor = 'text-green-600';
                    detailsHTML += `<p class="text-xs ${statusColor} mb-1"><strong>Action:</strong> ${item.details.action.replace(/\b\w/g, l => l.toUpperCase())}</p>`;
                }
                if (item.details.action === 'fund released') {
                    const statusColor = 'text-green-600';
                    detailsHTML += `<p class="text-xs ${statusColor} mb-1"><strong>Action:</strong> ${item.details.action.replace(/\b\w/g, l => l.toUpperCase())}</p>`;
                }
                if (item.details.disbursed_at) {
                    detailsHTML += `<p class="text-xs text-gray-600 mb-1"><strong>Disbursed At:</strong> ${formatDateTimeIST(item.details.disbursed_at)}</p>`;
                }
                
                detailsHTML += '</div>';
            }
            
            categoryHTML += `
                <div class="flex items-start space-x-3 p-3 bg-white rounded-lg border border-gray-200 mb-3 ${index === historyByCategory[category].length - 1 ? '' : 'border-b-0'}">
                    <div class="flex-shrink-0 mr-2">
                        <div class="w-4 h-4 rounded-full ${statusText  === '● In Progress' ? 'bg-brand-500' : 'bg-error-500'} flex items-center justify-center ${iconClass}">
                            <span class="text-xs font-medium ${iconTextClass}"></span>
                        </div>
                    </div>
                    <div class="flex-1 min-w-0">
                        <div class="flex items-center justify-between mb-1">
                            <h6 class="text-sm font-medium text-gray-900">${item.name}</h6>
                            <span class="text-xs ${statusClass} font-medium">${statusText}</span>
                        </div>
                        <p class="text-xs text-gray-600 mb-1">${item.description}</p>
                        ${item.timestamp ? `<p class="text-xs text-gray-400 mb-1">🕒 ${formatDateTimeIST(item.timestamp)}</p>` : ''}
                        ${detailsHTML}
                    </div>
                </div>
            `;
        });
        
        categoryHTML += '</div>';
        container.innerHTML = categoryHTML;
    });
    
    // If no history data, show basic steps
    if (sortedHistory.length === 0) {
        steps.forEach((step, index) => {
            const statusClass = step.status === 'completed' ? 'text-success-600' : 
                               step.status === 'current' ? 'text-brand-500' : 
                               step.status === 'failed' ? 'text-error-600' : 'text-gray-400';
            
            const statusText = step.status === 'completed' ? '✓ Completed' :
                              step.status === 'current' ? '● In Progress' : 
                              step.status === 'failed' ? '✗ Failed' : '○ Pending';
            
            const iconClass = step.status === 'completed' ? 'bg-success-500' : 
                             step.status === 'current' ? 'bg-brand-100' : 
                             step.status === 'failed' ? 'bg-error-100' : 'bg-gray-100';
            
            const iconTextClass = step.status === 'completed' ? 'text-success-500' : 
                                 step.status === 'current' ? 'text-brand-600' : 
                                 step.status === 'failed' ? 'text-error-600' : 'text-gray-400';
            
            const config = categoryConfig[step.category] || categoryConfig['system'];
            
            const html = `
                <div class="mb-4 p-4 ${config.bgColor} border ${config.borderColor} rounded-lg">
                    <div class="flex items-center mb-3">
                        <svg class="w-5 h-5 mr-2 ${config.color} dark:text-white/90" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="${config.icon}"></path>
                        </svg>
                        <h6 class="text-sm font-semibold ${config.color} dark:text-white/90">${config.name}</h6>
                    </div>
                    <div class="flex items-start space-x-3 p-3 bg-white rounded-lg border border-gray-200">
                        <div class="flex-shrink-0">
                            <div class="w-6 h-6 rounded-full flex items-center justify-center ${iconClass}">
                                <span class="text-xs font-medium ${iconTextClass}">1</span>
                            </div>
                        </div>
                        <div class="flex-1 min-w-0">
                            <div class="flex items-center justify-between mb-1">
                                <h6 class="text-sm font-medium text-gray-900">${step.name}</h6>
                                <span class="text-xs ${statusClass} font-medium">${statusText}</span>
                            </div>
                            <p class="text-xs text-gray-600 mb-1">${step.description}</p>
                            ${step.timestamp ? `<p class="text-xs text-gray-400 mb-1">🕒 ${formatDateTimeIST(step.timestamp)}</p>` : ''}
                        </div>
                    </div>
                </div>
            `;
            
            // Find the appropriate history container based on step category
            const containerId = `history-${step.category}`;
            const container = document.getElementById(containerId);
            if (container) {
                container.innerHTML = html;
            }
        });
    }
}

// ===== LOAN TRACKING MODAL FUNCTIONS (for disbursed fund release page) =====
// These functions are separate from the main application tracking and won't affect existing code

// Function to open loan tracking modal for disbursed fund release page
// function openLoanTrackingModal(loanRefNo) {

//     // Find the loan data for the given loanRefNo
//     let app;
    
//     // Check if data is in window.loanData (branch) or needs to be fetched (HQ)
//     if (window.loanData) {
//         app = window.loanData.find(item => item.loan_ref_no === loanRefNo);
//     } else {
//         // For HQ page, we need to find the data in the table row
//         const row = document.querySelector(`[data-loan*='"loan_ref_no": "${loanRefNo}"']`);
//         if (row) {
//             app = JSON.parse(row.getAttribute('data-loan'));
//         }
//     }
    
//     if (!app) {
//         alert('Loan data not found!');
//         return;
//     }

//     // Find the loan data for the given loanRefNo
//     // const app = (window.loanData.find(item => item.loan_ref_no === loanRefNo)) || loanRefNo;
//     // if (!app) {
//     //     alert('Loan data not found!');
//     //     return;
//     // }

//     // Create a container for the tracking UI with progress bar
//     const container = document.createElement('div');
//     container.innerHTML = `
//         <h3 class="text-lg font-semibold text-gray-800 dark:text-gray-200 mb-4 text-center border-b border-gray-800 dark:border-gray-200 pb-4">Loan Tracking</h3>
//         <div id="loan-progress-bar" class="w-full max-w-md mx-auto mb-6"></div>
//         <div class="mt-8 border-t border-gray-100 pt-6 custom-scrollbar overflow-y-auto max-h-[60vh]">
//             <div id="loan-history-agent" class="mb-6"></div>
//             <div id="loan-history-branch" class="mb-6"></div>
//             <div id="loan-history-hq" class="mb-6"></div>
//             <div id="loan-history-system" class="mb-6"></div>
//         </div>
//     `;

//     // Inject the container into the modal content
//     const modalContent = document.getElementById('loanTrackingModalContent');
//     modalContent.innerHTML = '';
//     modalContent.appendChild(container);

//     // Build progress bar based on loan history
//     buildLoanProgressBar(app);

//     // Build complete history
//     buildLoanHistory(app);

//     // Show the modal
//     document.getElementById('loanTrackingModal').classList.remove('hidden');
// }

// Function to build progress bar based on loan history
function buildLoanProgressBar(applicationData) {
    const progressContainer = document.getElementById('loan-progress-bar');
    if (!progressContainer) return;

    const isBranchCreated = applicationData && (!applicationData.agent || applicationData.created_by_branch);
    
    // Get status color function
    function getStatusColor(status) {
        const colors = {
            'pending': 'orange',
            'active': 'blue',
            'document_requested': 'red',
            'resubmitted': 'blue',
            'branch_document_accepted': 'green',
            'branch_approved': 'green',
            'rejected_by_branch': 'red',
            'document_requested_by_hq': 'red',
            'hq_approved': 'green',
            'hq_rejected': 'red',
            'disbursed': 'green',
            'disbursed_fund_released': 'green',
            'success': 'green',
            'reject': 'red',
            'inactive': 'gray'
        };
        return colors[status] || 'gray';
    }

    // Calculate progress based on application status
    let progressPercentage = 0;
    let progressText = '';
    let progressColor = 'bg-gray-300';
    
    if (applicationData.status === 'disbursed_fund_released') {
        progressPercentage = 100;
        progressText = 'Fund Released - 100% Complete';
        progressColor = 'bg-success-500';
    } else if (applicationData.status === 'disbursed') {
        progressPercentage = 80;
        progressText = 'Loan Disbursed - 80% Complete';
        progressColor = 'bg-success-500';
    } else if (applicationData.status === 'hq_approved') {
        progressPercentage = 60;
        progressText = 'HQ Approved - 60% Complete';
        progressColor = 'bg-success-500';
    } else if (applicationData.status === 'branch_approved') {
        progressPercentage = 40;
        progressText = 'Branch Approved - 40% Complete';
        progressColor = 'bg-success-500';
    } else if (applicationData.status === 'pending' || applicationData.status === 'active') {
        progressPercentage = 20;
        progressText = 'Application Submitted - 20% Complete';
        progressColor = 'bg-brand-500';
    } else if (applicationData.status === 'hq_rejected' || applicationData.status === 'rejected_by_branch') {
        progressPercentage = 0;
        progressText = 'Application Rejected';
        progressColor = 'bg-error-500';
    }

    // Build progress bar HTML
    const progressHTML = `
        <div class="text-center">
            <p class="text-sm font-medium text-gray-700">${progressText}</p>
            <p class="text-xs text-gray-500 mt-1">Loan Reference: ${applicationData.loan_ref_no}</p>
        </div>
    `;
    
    progressContainer.innerHTML = progressHTML;
}

// Function to build complete history for loan tracking modal
function buildCompleteHistoryForLoan(applicationData) {
    const history = [];
    const isBranchCreated = applicationData && (!applicationData.agent || applicationData.created_by_branch);
    
    // Add submission
    if (applicationData?.submitted_at) {
        history.push({
            id: isBranchCreated ? 'branch_submission' : 'agent_submission',
            name: isBranchCreated ? 'Branch Submission' : 'Agent Submission',
            description: isBranchCreated ? 'Application submitted by branch' : 'Application submitted by agent',
            status: 'completed',
            timestamp: applicationData.submitted_at,
            category: isBranchCreated ? 'branch' : 'agent',
            details: isBranchCreated ? {
                branch: applicationData.branch_name || applicationData.branch || '',
                submitted_at: applicationData.submitted_at
            } : {
                agent: applicationData.agent?.full_name,
                submitted_at: applicationData.submitted_at
            }
        });
    }
    
    // Add HQ document requests (for branch-created)
    if (isBranchCreated && applicationData?.document_requests) {
        applicationData.document_requests.forEach((request, index) => {
            const requestStatus = request.is_resolved ? 'completed' : 'current';
            const category = 'hq';
            history.push({
                id: `hq_document_request_${index}`,
                name: 'HQ Document Request',
                description: `${request.document_type.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase())} requested - ${request.reason.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase())}`,
                status: requestStatus,
                timestamp: request.requested_at,
                category: category,
                details: {
                    document_type: request.document_type,
                    reason: request.reason,
                    comment: request.comment,
                    requested_by: request.requested_by || request.requested_by_hq,
                    requested_at: request.requested_at,
                    is_resolved: request.is_resolved,
                    resolved_at: request.resolved_at
                }
            });
        });
    } else if (applicationData?.document_requests) {
        // Agent-created: keep original logic
        applicationData.document_requests.forEach((request, index) => {
            const requestStatus = request.is_resolved ? 'completed' : 'current';
            const category = request.category || (request.requested_by_hq ? 'hq' : 'branch');
            history.push({
                id: `document_request_${index}`,
                name: (category === 'branch') ? 'Branch Document Request' : 'HQ Document Request',
                description: `${request.document_type.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase())} requested - ${request.reason.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase())}`,
                status: requestStatus,
                timestamp: request.requested_at,
                category: category,
                details: {
                    document_type: request.document_type,
                    reason: request.reason,
                    comment: request.comment,
                    requested_by: request.requested_by || request.requested_by_hq,
                    requested_at: request.requested_at,
                    is_resolved: request.is_resolved,
                    resolved_at: request.resolved_at
                }
            });
        });
    }
    
    // Add branch resubmission (for branch-created)
    if (isBranchCreated && applicationData?.document_reuploads) {
        applicationData.document_reuploads.forEach((reupload, index) => {
            history.push({
                id: `branch_resubmission_${index}`,
                name: 'Branch Re-uploaded',
                description: `${reupload.document_type.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase())} re-uploaded`,
                status: 'completed',
                timestamp: reupload.uploaded_at,
                category: 'branch',
                details: {
                    document_type: reupload.document_type,
                    agent_note: reupload.agent_note,
                    uploaded_by: reupload.uploaded_by,
                    uploaded_at: reupload.uploaded_at
                }
            });
        });
    } else if (applicationData?.document_reuploads) {
        // Agent-created: keep original logic
        applicationData.document_reuploads.forEach((reupload, index) => {
            history.push({
                id: `document_reupload_${index}`,
                name: 'Document Reupload',
                description: `${reupload.document_type.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase())} reuploaded`,
                status: 'completed',
                timestamp: reupload.uploaded_at,
                category: 'agent',
                details: {
                    document_type: reupload.document_type,
                    agent_note: reupload.agent_note,
                    uploaded_by: reupload.uploaded_by,
                    uploaded_at: reupload.uploaded_at
                }
            });
        });
    }
    
    // Add HQ document reviews (for branch-created)
    if (isBranchCreated && applicationData?.document_reviews) {
        applicationData.document_reviews.forEach((review, index) => {
            const reviewStatus = review.decision === 'approved' ? 'completed' : 
                               review.decision === 'rejected' || review.decision === 'request_again' ? 'failed' : 'current';
            history.push({
                id: `hq_document_review_${index}`,
                name: 'HQ Document Review',
                description: `${review.document_type ? review.document_type.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase()) + ' - ' : ''}${review.decision.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase())}`,
                status: reviewStatus,
                timestamp: review.reviewed_at,
                category: 'hq',
                details: {
                    document_type: review.document_type,
                    decision: review.decision,
                    review_comment: review.review_comment,
                    reviewed_by: review.reviewed_by,
                    reviewed_at: review.reviewed_at
                }
            });
        });
    } else if (applicationData?.document_reviews) {
        // Agent-created: keep original logic
        applicationData.document_reviews.forEach((review, index) => {
            const reviewStatus = review.decision === 'approved' ? 'completed' : 
                               review.decision === 'rejected' || review.decision === 'request_again' ? 'failed' : 'current';
            history.push({
                id: `standalone_review_${index}`,
                name: 'Document Review',
                description: `${review.document_type ? review.document_type.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase()) + ' - ' : ''}${review.decision.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase())}`,
                status: reviewStatus,
                timestamp: review.reviewed_at,
                category: 'branch',
                details: {
                    document_type: review.document_type,
                    decision: review.decision,
                    review_comment: review.review_comment,
                    reviewed_by: review.reviewed_by,
                    reviewed_at: review.reviewed_at
                }
            });
        });
    }
    
    // Add branch approval (for branch-created) - check historical indicators
    const shouldShowBranchApproval = isBranchCreated ? 
        (applicationData?.status === 'branch_approved' || 
         applicationData?.ever_branch_approved || 
         ['hq_approved', 'hq_rejected', 'disbursed', 'disbursed_fund_released'].includes(applicationData?.status)) :
        (applicationData?.status === 'branch_approved' || 
         applicationData?.ever_branch_approved || 
         ['hq_approved', 'hq_rejected', 'disbursed', 'disbursed_fund_released'].includes(applicationData?.status));
    
    if (shouldShowBranchApproval) {
        history.push({
            id: 'branch_approval',
            name: 'Branch Approval',
            description: 'Application approved by branch',
            status: 'completed',
            timestamp: applicationData.branch_approved_at || applicationData.approved_at || applicationData.updated_at || applicationData.submitted_at,
            category: 'branch',
            details: {
                action: 'approved',
                status: applicationData.status,
                approved_by: applicationData.branch_approver || null
            }
        });
    }
    
    // Add HQ approval/rejection - check historical indicators
    const shouldShowHQApproval = applicationData?.status === 'hq_approved' || 
                               applicationData?.hq_approved_at || 
                               ['disbursed', 'disbursed_fund_released'].includes(applicationData?.status);
    
    if (shouldShowHQApproval) {
        history.push({
            id: 'hq_approval',
            name: 'HQ Approval',
            description: 'Application approved by headquarters',
            status: 'completed',
            timestamp: applicationData.hq_approved_at || applicationData.approved_at || applicationData.updated_at || applicationData.submitted_at,
            category: 'hq',
            details: {
                action: 'approved',
                status: applicationData.status,
                approved_by: applicationData.hq_approver || null
            }
        });
    } else if (applicationData?.status === 'hq_rejected') {
        history.push({
            id: 'hq_rejection',
            name: 'HQ Rejection',
            description: 'Application rejected by headquarters',
            status: 'failed',
            timestamp: applicationData.submitted_at,
            category: 'hq',
            details: {
                action: 'rejected',
                status: applicationData.status
            }
        });
    }
    
    // Add disbursement status - check historical indicators
    const shouldShowDisbursement = applicationData?.status === 'disbursed' || 
                                 applicationData?.disbursed_at || 
                                 applicationData?.status === 'disbursed_fund_released';
    
    if (shouldShowDisbursement) {
        history.push({
            id: 'loan_disbursed',
            name: 'Loan Disbursed',
            description: 'Loan amount disbursed to customer',
            status: 'completed',
            timestamp: applicationData.disbursed_at || applicationData.updated_at || applicationData.submitted_at,
            category: 'system',
            details: {
                action: 'disbursed',
                status: applicationData.status,
                disbursed_at: applicationData.disbursed_at
            }
        });
    }
    
    // Add disbursed fund released status - check historical indicators
    const shouldShowFundRelease = applicationData?.status === 'disbursed_fund_released' || 
                                applicationData?.disbursed_at; // If disbursed_at exists, fund release is likely to have happened
    
    if (shouldShowFundRelease) {
        history.push({
            id: 'fund_released',
            name: 'Fund Released',
            description: 'Loan disbursed and funds released to customer',
            status: 'completed',
            timestamp: applicationData.disbursed_at || applicationData.updated_at || applicationData.submitted_at,
            category: 'system',
            details: {
                action: 'fund released',
                status: applicationData.status,
                disbursed_at: applicationData.disbursed_at
            }
        });
    }
    
    // Rejected/inactive
    if (applicationData?.status === 'reject' || applicationData?.status === 'inactive') {
        history.push({
            id: 'application_rejected',
            name: 'Application Rejected',
            description: 'Application rejected or inactive',
            status: 'failed',
            timestamp: applicationData.updated_at || applicationData.submitted_at,
            category: 'system',
            details: {
                action: 'rejected',
                status: applicationData.status
            }
        });
    }
    
    return history;
}

// Function to build loan history
function buildLoanHistory(applicationData) {
    // Clear all history containers
    const historyContainers = ['loan-history-agent', 'loan-history-branch', 'loan-history-hq', 'loan-history-system'];
    historyContainers.forEach(containerId => {
        const container = document.getElementById(containerId);
        if (container) container.innerHTML = '';
    });

    // Build complete history using the existing logic from application_tracking.js
    const history = buildCompleteHistoryForLoan(applicationData);
    
    // Sort history by timestamp (oldest first)
    const sortedHistory = [...history].sort((a, b) => {
        if (!a.timestamp && !b.timestamp) return 0;
        if (!a.timestamp) return 1;
        if (!b.timestamp) return -1;
        return new Date(a.timestamp) - new Date(b.timestamp);
    });
    
    // Group history by category
    const historyByCategory = {};
    sortedHistory.forEach(item => {
        if (!historyByCategory[item.category]) {
            historyByCategory[item.category] = [];
        }
        historyByCategory[item.category].push(item);
    });
    
    // Category configuration
    const categoryConfig = {
        'agent': {
            name: 'Agent Actions',
            icon: 'M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z',
            color: 'text-blue-600',
            bgColor: 'bg-blue-50',
            borderColor: 'border-blue-200'
        },
        'branch': {
            name: 'Branch Actions',
            icon: 'M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16m14 0h2m-2 0h-5m-9 0H3m2 0h5M9 7h1m-1 4h1m4-4h1m-1 4h1m-5 10v-5a1 1 0 011-1h2a1 1 0 011 1v5m-4 0h4',
            color: 'text-green-600',
            bgColor: 'bg-green-50',
            borderColor: 'border-green-200'
        },
        'hq': {
            name: 'Headquarters Actions',
            icon: 'M21 13.255A23.931 23.931 0 0112 15c-3.183 0-6.22-.62-9-1.745M16 6V4a2 2 0 00-2-2h-4a2 2 0 00-2-2v2m8 0V6a2 2 0 012 2v6a2 2 0 01-2 2H8a2 2 0 01-2-2V8a2 2 0 012-2V6',
            color: 'text-purple-600',
            bgColor: 'bg-purple-50',
            borderColor: 'border-purple-200'
        },
        'system': {
            name: 'System Actions',
            icon: 'M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z',
            color: 'text-gray-600',
            bgColor: 'bg-gray-50',
            borderColor: 'border-gray-200'
        }
    };
    
    // Render history for each category
    Object.keys(historyByCategory).forEach(category => {
        const containerId = `loan-history-${category}`;
        const container = document.getElementById(containerId);
        if (!container) return;
        
        const config = categoryConfig[category] || categoryConfig['system'];
        
        let categoryHTML = `
            <div class="mb-4 p-4 ${config.bgColor} ${config.borderColor} rounded-lg">
                <div class="flex items-center mb-3">
                    <svg class="w-5 h-5 mr-2 ${config.color} dark:text-white/90" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="${config.icon}"></path>
                    </svg>
                    <h6 class="text-sm font-semibold ${config.color} dark:text-white/90">${config.name}</h6>
                    <span class="ml-auto text-xs text-gray-500">${historyByCategory[category].length} action(s)</span>
                </div>
        `;
        
        historyByCategory[category].forEach((item, index) => {
            const statusClass = item.status === 'completed' ? 'text-success-600' : 
                               item.status === 'current' ? 'text-brand-500' : 
                               item.status === 'failed' ? 'text-error-600' : 'text-gray-400';
            
            const statusText = item.status === 'completed' ? '✓ Completed' :
                              item.status === 'current' ? '● In Progress' : 
                              item.status === 'failed' ? '✗ Failed' : '○ Pending';
            
            const iconClass = item.status === 'completed' ? 'bg-success-500' : 
                             item.status === 'current' ? 'bg-brand-100' : 
                             item.status === 'failed' ? 'bg-error-100' : 'bg-gray-100';
            
            const iconTextClass = item.status === 'completed' ? 'text-success-500' : 
                                 item.status === 'current' ? 'text-brand-600' : 
                                 item.status === 'failed' ? 'text-error-600' : 'text-gray-400';
            
            // Build details section
            let detailsHTML = '';
            if (item.details) {
                detailsHTML += '<div class="mt-2 p-2 bg-white rounded border-l-4 border-gray-300">';
                
                if (item.details.agent_note) {
                    detailsHTML += `<p class="text-xs text-gray-600 mb-1"><strong>Agent Note:</strong> ${item.details.agent_note}</p>`;
                }
                if (item.details.review_comment) {
                    detailsHTML += `<p class="text-xs text-gray-600 mb-1"><strong>Review Comment:</strong> ${item.details.review_comment}</p>`;
                }
                if (item.details.uploaded_by) {
                    detailsHTML += `<p class="text-xs text-gray-600 mb-1"><strong>Uploaded by:</strong> ${item.details.uploaded_by}</p>`;
                }
                if (item.details.reviewed_by) {
                    detailsHTML += `<p class="text-xs text-gray-600 mb-1"><strong>Reviewed by:</strong> ${item.details.reviewed_by}</p>`;
                }
                if (item.details.requested_by) {
                    detailsHTML += `<p class="text-xs text-gray-600 mb-1"><strong>Requested by:</strong> ${item.details.requested_by}</p>`;
                }
                if (item.details.document_type) {
                    detailsHTML += `<p class="text-xs text-gray-600 mb-1"><strong>Document:</strong> ${item.details.document_type.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase())}</p>`;
                }
                if (item.details.reason) {
                    detailsHTML += `<p class="text-xs text-gray-600 mb-1"><strong>Reason:</strong> ${item.details.reason.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase())}</p>`;
                }
                if (item.details.comment) {
                    detailsHTML += `<p class="text-xs text-gray-600 mb-1"><strong>Comment:</strong> ${item.details.comment}</p>`;
                }
                if (item.details.decision) {
                    const decisionColor = item.details.decision === 'approved' ? 'text-green-600' : 
                                        item.details.decision === 'rejected' ? 'text-red-600' : 'text-yellow-600';
                    detailsHTML += `<p class="text-xs ${decisionColor} mb-1"><strong>Decision:</strong> ${item.details.decision.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase())}</p>`;
                }
                if (item.details.is_resolved !== undefined) {
                    const resolvedStatus = item.details.is_resolved ? 'text-green-600' : 'text-yellow-600';
                    const resolvedText = item.details.is_resolved ? 'Resolved' : 'Pending';
                    detailsHTML += `<p class="text-xs ${resolvedStatus} mb-1"><strong>Status:</strong> ${resolvedText}</p>`;
                }
                if (item.details.action === 'approved') {
                    const actionColor = item.details.action === 'approved' ? 'text-green-600' : 'text-red-600';
                    detailsHTML += `<p class="text-xs ${actionColor} mb-1"><strong>Action:</strong> ${item.details.action.replace(/\b\w/g, l => l.toUpperCase())}</p>`;
                }
                if (item.details.action === 'disbursed') {
                    const statusColor = 'text-green-600';
                    detailsHTML += `<p class="text-xs ${statusColor} mb-1"><strong>Action:</strong> ${item.details.action.replace(/\b\w/g, l => l.toUpperCase())}</p>`;
                }
                if (item.details.action === 'fund released') {
                    const statusColor = 'text-green-600';
                    detailsHTML += `<p class="text-xs ${statusColor} mb-1"><strong>Action:</strong> ${item.details.action.replace(/\b\w/g, l => l.toUpperCase())}</p>`;
                }
                if (item.details.disbursed_at) {
                    detailsHTML += `<p class="text-xs text-gray-600 mb-1"><strong>Disbursed At:</strong> ${formatDateTimeIST(item.details.disbursed_at)}</p>`;
                }
                
                detailsHTML += '</div>';
            }
            
            categoryHTML += `
                <div class="flex items-start space-x-3 p-3 bg-white rounded-lg border border-gray-200 mb-3 ${index === historyByCategory[category].length - 1 ? '' : 'border-b-0'}">
                    <div class="flex-shrink-0 mr-2">
                        <div class="w-4 h-4 rounded-full ${statusText  === '● In Progress' ? 'bg-brand-500' : 'bg-error-500'} flex items-center justify-center ${iconClass}">
                            <span class="text-xs font-medium ${iconTextClass}"></span>
                        </div>
                    </div>
                    <div class="flex-1 min-w-0">
                        <div class="flex items-center justify-between mb-1">
                            <h6 class="text-sm font-medium text-gray-900">${item.name}</h6>
                            <span class="text-xs ${statusClass} font-medium">${statusText}</span>
                        </div>
                        <p class="text-xs text-gray-600 mb-1">${item.description}</p>
                        ${item.timestamp ? `<p class="text-xs text-gray-400 mb-1">🕒 ${formatDateTimeIST(item.timestamp)}</p>` : ''}
                        ${detailsHTML}
                    </div>
                </div>
            `;
        });
        
        categoryHTML += '</div>';
        container.innerHTML = categoryHTML;
    });
}
