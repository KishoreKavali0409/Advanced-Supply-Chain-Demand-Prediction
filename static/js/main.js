/**
 * Smart Demand Forecast - Main JavaScript
 */

// Wait for DOM content to be fully loaded
document.addEventListener('DOMContentLoaded', function() {
  
  // Initialize tooltips
  var tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
  tooltipTriggerList.map(function (tooltipTriggerEl) {
    return new bootstrap.Tooltip(tooltipTriggerEl);
  });
  
  // File upload handling with preview
  const fileInput = document.getElementById('dataset');
  if (fileInput) {
    fileInput.addEventListener('change', function(e) {
      const fileName = e.target.files[0]?.name;
      const fileSize = e.target.files[0]?.size;
      
      if (fileName) {
        // Display filename
        let fileInfoElement = document.getElementById('file-info');
        if (!fileInfoElement) {
          fileInfoElement = document.createElement('div');
          fileInfoElement.id = 'file-info';
          fileInfoElement.className = 'alert alert-info mt-2';
          fileInput.parentNode.appendChild(fileInfoElement);
        }
        
        // Format file size
        const formattedSize = formatFileSize(fileSize);
        fileInfoElement.innerHTML = `
          <i class="fas fa-file-csv me-2"></i>
          Selected file: <strong>${fileName}</strong> (${formattedSize})
        `;
        
        // Validate file type
        if (!fileName.toLowerCase().endsWith('.csv')) {
          showError('Please select a CSV file.');
          fileInput.value = '';
          if (fileInfoElement) fileInfoElement.remove();
        }
      }
    });
  }
  
  // Forecast form validation
  const forecastForm = document.getElementById('forecast-form');
  if (forecastForm) {
    forecastForm.addEventListener('submit', function(e) {
      const productSelect = document.getElementById('product');
      const daysInput = document.getElementById('days');
      
      if (productSelect.value === '') {
        e.preventDefault();
        showError('Please select a product.');
        return;
      }
      
      const days = parseInt(daysInput.value);
      if (isNaN(days) || days < 1 || days > 90) {
        e.preventDefault();
        showError('Please enter a valid number of days (1-90).');
        return;
      }
      
      // Show loading indicator
      showLoading('Generating forecast...');
    });
  }
  
  // Upload form validation
  const uploadForm = document.getElementById('upload-form');
  if (uploadForm) {
    uploadForm.addEventListener('submit', function(e) {
      if (!fileInput.files[0]) {
        e.preventDefault();
        showError('Please select a file to upload.');
        return;
      }
      
      // Show loading indicator
      showLoading('Uploading and processing data...');
    });
  }
  
  // Helper functions
  function formatFileSize(bytes) {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
  }
  
  function showError(message) {
    let errorAlert = document.getElementById('error-alert');
    if (!errorAlert) {
      errorAlert = document.createElement('div');
      errorAlert.id = 'error-alert';
      errorAlert.className = 'alert alert-danger alert-dismissible fade show mt-3';
      errorAlert.setAttribute('role', 'alert');
      
      const closeButton = document.createElement('button');
      closeButton.type = 'button';
      closeButton.className = 'btn-close';
      closeButton.setAttribute('data-bs-dismiss', 'alert');
      closeButton.setAttribute('aria-label', 'Close');
      
      errorAlert.appendChild(closeButton);
      document.querySelector('.card-body').prepend(errorAlert);
    }
    
    errorAlert.innerHTML = `
      <i class="fas fa-exclamation-triangle me-2"></i>
      <strong>Error:</strong> ${message}
      <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
    `;
  }
  
  function showLoading(message = 'Loading...') {
    // Create loading overlay
    const loadingEl = document.createElement('div');
    loadingEl.className = 'loading-spinner';
    loadingEl.innerHTML = `
      <div class="spinner-border text-light" role="status">
        <span class="visually-hidden">Loading...</span>
      </div>
      <div class="text-light mt-3">${message}</div>
    `;
    document.body.appendChild(loadingEl);
  }
  
  // Dynamically adjust plot size on window resize
  window.addEventListener('resize', function() {
    const plotElement = document.getElementById('forecastChart');
    if (plotElement && window.Plotly) {
      Plotly.Plots.resize(plotElement);
    }
  });
  
});
