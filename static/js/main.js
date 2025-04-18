// Main JavaScript for Smart Demand Forecast

document.addEventListener('DOMContentLoaded', function() {
  console.log('Smart Demand Forecast application initialized');
  
  // Format file sizes in human readable format
  function formatFileSize(bytes) {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
  }
  
  // Show error messages
  function showError(message) {
    const errorContainer = document.createElement('div');
    errorContainer.className = 'alert alert-danger alert-dismissible fade show';
    errorContainer.innerHTML = `
      <i class="fas fa-exclamation-triangle me-2"></i>
      <strong>Error:</strong> ${message}
      <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
    `;
    
    // Find a suitable container
    const container = document.querySelector('.container') || document.body;
    container.prepend(errorContainer);
    
    // Auto-dismiss after 10 seconds
    setTimeout(() => {
      const bsAlert = new bootstrap.Alert(errorContainer);
      bsAlert.close();
    }, 10000);
  }
  
  // Show loading indicator
  function showLoading(message = 'Loading...') {
    const loadingDiv = document.createElement('div');
    loadingDiv.className = 'loading-spinner';
    loadingDiv.innerHTML = `
      <div class="spinner-container">
        <div class="spinner-border text-primary" role="status">
          <span class="visually-hidden">Loading...</span>
        </div>
        <p class="mt-2 text-white">${message}</p>
      </div>
    `;
    document.body.appendChild(loadingDiv);
    return loadingDiv;
  }
  
  // Hide loading indicator
  function hideLoading(loadingElement) {
    if (loadingElement && loadingElement.parentNode) {
      loadingElement.parentNode.removeChild(loadingElement);
    }
  }
  
  // Initialize file upload functionality if present
  const fileUpload = document.getElementById('dataset');
  if (fileUpload) {
    fileUpload.addEventListener('change', function(e) {
      const fileName = e.target.files[0]?.name || 'No file selected';
      const fileSize = e.target.files[0]?.size || 0;
      
      // Update file info display if it exists
      const fileInfo = document.getElementById('file-info');
      if (fileInfo) {
        fileInfo.innerHTML = `
          <strong>File:</strong> ${fileName} <br>
          <strong>Size:</strong> ${formatFileSize(fileSize)}
        `;
      }
      
      // Validate file type
      if (fileSize > 0 && !fileName.toLowerCase().endsWith('.csv')) {
        showError('Please select a CSV file');
        fileUpload.value = '';
        if (fileInfo) fileInfo.innerHTML = '';
      }
      
      // Validate file size (16MB max)
      if (fileSize > 16 * 1024 * 1024) {
        showError('File size exceeds 16MB limit');
        fileUpload.value = '';
        if (fileInfo) fileInfo.innerHTML = '';
      }
    });
  }
  
  // Initialize form submissions to show loading indicator
  const forms = document.querySelectorAll('form');
  forms.forEach(form => {
    form.addEventListener('submit', function() {
      // Don't show loading for clear dataset form
      if (form.action.includes('clear_dataset')) {
        return true;
      }
      
      const loadingMessage = form.dataset.loadingMessage || 'Processing request...';
      showLoading(loadingMessage);
      return true;
    });
  });
  
  // Initialize tooltips
  const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
  tooltipTriggerList.map(function (tooltipTriggerEl) {
    return new bootstrap.Tooltip(tooltipTriggerEl);
  });
  
});