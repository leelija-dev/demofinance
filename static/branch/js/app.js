// Import ApexCharts
import ApexCharts from 'apexcharts';

// Make ApexCharts globally available for any components that might need it
window.ApexCharts = ApexCharts;

// Chart instances will be stored here for cleanup
window.chartInstances = {};

// Get Alpine from window since it's loaded via CDN
const Alpine = window.Alpine;

// Import chart initializers
import chart01 from './components/charts/chart-01';
import chart02 from './components/charts/chart-02';
import chart03 from './components/charts/chart-03';
import map01 from './components/map-01';

// ApexCharts is now imported and available

// Initialize components when Alpine is ready
document.addEventListener('alpine:init', () => {
  console.log('Alpine.js is ready, initializing components...');
  initComponents();
});

// Also try initializing when the page is fully loaded
if (document.readyState === 'complete') {
  initComponents();
} else {
  window.addEventListener('load', initComponents);
}

// Function to initialize a single component (chart or map)
function initComponent(componentId, initFunction, isMap = false) {
  const element = document.getElementById(componentId);
  if (!element) {
    console.warn(`Element not found: #${componentId}`);
    return null;
  }

  // Check if there's a global instance to clean up
  const globalInstanceName = `${componentId}Instance`;
  if (window[globalInstanceName]) {
    try {
      console.log(`Cleaning up previous instance of: ${componentId}`);
      if (isMap && window[globalInstanceName].cleanup) {
        window[globalInstanceName].cleanup();
      } else if (window[globalInstanceName].destroy) {
        window[globalInstanceName].destroy();
      }
      window[globalInstanceName] = null;
    } catch (e) {
      console.error(`Error cleaning up ${componentId}:`, e);
    }
  }

  try {
    console.log(`Initializing ${isMap ? 'map' : 'chart'}: ${componentId}`);
    const instance = initFunction();
    window[globalInstanceName] = instance; // Store for cleanup
    return instance;
  } catch (error) {
    console.error(`Error initializing ${componentId}:`, error);
    return null;
  }
}

// Function to initialize all components
function initComponents() {
  console.log('Initializing components...');
  
  // Try to initialize each component
  const componentsInitialized = [
    initComponent('chartOne', chart01),
    initComponent('chartTwo', chart02),
    initComponent('chartThree', chart03),
    initComponent('mapOne', map01, true) // Initialize the map with isMap flag
  ];
  
  console.log(`Components initialized: ${componentsInitialized.filter(Boolean).length} of ${componentsInitialized.length}`);
  
  // If any component failed to initialize, try again in 500ms
  if (componentsInitialized.some(initialized => !initialized)) {
    console.log('Some components not initialized, retrying...');
    setTimeout(initComponents, 500);
  }
}

// Initialize components when the DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
  console.log('DOM fully loaded, initializing components...');
  
  // Initialize Alpine.js if available
  if (window.Alpine) {
    window.Alpine.start();
    console.log('Alpine.js initialized');
  }
  
  // Initialize components with a small delay to ensure all components are mounted
  setTimeout(initComponents, 300);
});

// Also try initializing when the page is fully loaded
// Initialize components when the window is fully loaded
window.addEventListener('load', () => {
  console.log('Window fully loaded, initializing components...');
  initComponents();
});
