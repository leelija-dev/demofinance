import ApexCharts from "apexcharts";

// ===== chartTwo
const chart02 = () => {
  const chartTwoOptions = {
    series: [75.55],
    colors: ["#465FFF"],
    chart: {
      fontFamily: "Outfit, sans-serif",
      type: "radialBar",
      height: 330,
      sparkline: {
        enabled: true,
      },
    },
    plotOptions: {
      radialBar: {
        startAngle: -90,
        endAngle: 90,
        hollow: {
          size: "80%",
        },
        track: {
          background: "#E4E7EC",
          strokeWidth: "100%",
          margin: 5, // margin is in pixels
        },
        dataLabels: {
          name: {
            show: false,
          },
          value: {
            fontSize: "36px",
            fontWeight: "600",
            offsetY: 60,
            color: "#1D2939",
            formatter: function (val) {
              return val + "%";
            },
          },
        },
      },
    },
    fill: {
      type: "solid",
      colors: ["#465FFF"],
    },
    stroke: {
      lineCap: "round",
    },
    labels: ["Progress"],
  };

  const chartSelector = document.querySelectorAll("#chartTwo");

  if (chartSelector.length) {
    const chartElement = document.getElementById("chartTwo");
    if (!chartElement) return null;
  
    // Clean up any existing chart
    if (window.chartTwoInstance) {
      try {
        window.chartTwoInstance.destroy();
      } catch (e) {
        console.error('Error cleaning up previous chart:', e);
      }
    }
  
    // Create and render new chart
    const chart = new ApexCharts(chartElement, chartTwoOptions);
    chart.render();
  
    // Store reference for cleanup
    window.chartTwoInstance = chart;
    return chart;
  }
};

export default chart02;
