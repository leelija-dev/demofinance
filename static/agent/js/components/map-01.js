// Simple SVG-based map implementation
const map01 = () => {
  const mapElement = document.getElementById("mapOne");
  if (!mapElement) {
    console.warn("Map container not found: #mapOne");
    return null;
  }

  // Clean up any existing map instance
  if (window.mapOneInstance) {
    try {
      window.mapOneInstance.cleanup();
    } catch (e) {
      console.error('Error cleaning up previous map:', e);
    }
  }

  try {
    console.log("Initializing simple SVG map...");
    
    // Create SVG element
    const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
    svg.setAttribute("viewBox", "0 0 800 500");
    svg.style.width = '100%';
    svg.style.height = '100%';
    
    // Add a simple rectangle as the map background
    const bg = document.createElementNS("http://www.w3.org/2000/svg", "rect");
    bg.setAttribute("width", "100%");
    bg.setAttribute("height", "100%");
    bg.setAttribute("fill", "#f0f0f0");
    svg.appendChild(bg);
    
    // Add some sample markers
    const markers = [
      { name: 'Egypt', x: 400, y: 250 },
      { name: 'United Kingdom', x: 450, y: 150 },
      { name: 'United States', x: 200, y: 200 }
    ];
    
    markers.forEach(marker => {
      const markerGroup = document.createElementNS("http://www.w3.org/2000/svg", "g");
      
      // Create circle
      const circle = document.createElementNS("http://www.w3.org/2000/svg", "circle");
      circle.setAttribute("cx", marker.x);
      circle.setAttribute("cy", marker.y);
      circle.setAttribute("r", 5);
      circle.setAttribute("fill", "#fff");
      circle.setAttribute("stroke", "#465fff");
      circle.setAttribute("stroke-width", "2");
      
      // Add hover effect
      circle.addEventListener('mouseover', () => {
        circle.setAttribute("fill", "#465fff");
      });
      circle.addEventListener('mouseout', () => {
        circle.setAttribute("fill", "#fff");
      });
      
      // Add title for tooltip
      const title = document.createElementNS("http://www.w3.org/2000/svg", "title");
      title.textContent = marker.name;
      
      markerGroup.appendChild(title);
      markerGroup.appendChild(circle);
      svg.appendChild(markerGroup);
    });
    
    // Clear and add the SVG to the container
    mapElement.innerHTML = '';
    mapElement.appendChild(svg);
    
    // Store the map instance with cleanup function
    window.mapOneInstance = {
      element: svg,
      cleanup: () => {
        mapElement.innerHTML = '';
      }
    };
    
    return window.mapOneInstance;
  } catch (error) {
    console.error("Error initializing map:", error);
    return null;
  }
};

export default map01;
