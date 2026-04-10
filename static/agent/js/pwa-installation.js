document.addEventListener("DOMContentLoaded", function () {
  // DOM elements
  const pwaInstallPopup = document.getElementById("pwaInstallPopup");
  const pwaPopupOverlay = document.getElementById("pwaPopupOverlay");
  const pwaCloseBtn = document.getElementById("pwaCloseBtn");
  const pwaLaterBtn = document.getElementById("pwaLaterBtn");
  const pwaInstallBtn = document.getElementById("pwaInstallBtn");
  const pwaInstructions = document.getElementById("pwaInstructions");
  const pwaInstructionsClose = document.getElementById("pwaInstructionsClose");
  const btnText = pwaInstallBtn.querySelector(".btn-text");

  // PWA installation variables
  let deferredPrompt = null;
  let isPWAInstalled = false;
  let isInstalling = false;

  // Check if screen width is less than 1024px
  function isMobileScreen() {
    return window.innerWidth < 1025;
  }

  // Check if PWA is already installed
  function checkPWAInstallation() {
    // Check if the app is running in standalone mode (installed)
    if (window.matchMedia("(display-mode: standalone)").matches) {
      isPWAInstalled = true;
      localStorage.setItem("pwaInstalled", "true");
      return true;
    }

    // Check for other installation indicators
    if (window.navigator.standalone) {
      isPWAInstalled = true;
      localStorage.setItem("pwaInstalled", "true");
      return true;
    }

    // Check localStorage
    if (localStorage.getItem("pwaInstalled") === "true") {
      isPWAInstalled = true;
      return true;
    }

    return false;
  }

  // Show the popup
  function showPopup() {
    if (isMobileScreen() && !checkPWAInstallation()) {
      // Small delay to ensure page is loaded
      setTimeout(() => {
        pwaInstallPopup.classList.add("show");
        pwaPopupOverlay.classList.add("show");
      }, 1500);
    }
  }

  // Hide the popup
  function hidePopup() {
    pwaInstallPopup.classList.remove("show");
    pwaPopupOverlay.classList.remove("show");
  }

  // Dismiss popup (now just hides it for current session)
  function dismissPopup() {
    hidePopup();
  }

  // Show installation instructions
  function showInstructions() {
    pwaInstructions.classList.add("show");
    pwaPopupOverlay.classList.add("show");
  }

  // Hide installation instructions
  function hideInstructions() {
    pwaInstructions.classList.remove("show");
    pwaPopupOverlay.classList.remove("show");
  }

  // Set installing state
  function setInstallingState(installing) {
    isInstalling = installing;
    if (installing) {
      pwaInstallBtn.disabled = true;
      btnText.innerHTML =
        '<span class="pwa-loading"></span> Installing...';
    } else {
      pwaInstallBtn.disabled = false;
      btnText.textContent = "Install";
    }
  }

  // Detect browser and show appropriate installation method
  function getInstallMethod() {
    const userAgent = navigator.userAgent.toLowerCase();

    // Chrome, Edge, Opera
    if (
      userAgent.includes("chrome") ||
      userAgent.includes("edg") ||
      userAgent.includes("opr")
    ) {
      return "chrome";
    }
    // Safari
    else if (
      userAgent.includes("safari") &&
      !userAgent.includes("chrome")
    ) {
      return "safari";
    }
    // Firefox
    else if (userAgent.includes("firefox")) {
      return "firefox";
    }
    // Samsung Internet
    else if (userAgent.includes("samsung")) {
      return "samsung";
    }

    return "generic";
  }

  // Show browser-specific installation instructions
  function showBrowserSpecificInstructions() {
    const browser = getInstallMethod();
    const instructions = document.getElementById("pwaInstructions");

    let steps = "";

    switch (browser) {
      case "chrome":
      case "edg":
      case "opr":
      case "firefox":
      case "samsung":
        steps = `
          <ol>
            <li>Tap the <strong>Menu</strong> button <i class="fas fa-ellipsis-vertical"></i> (three dots) in the top right</li>
            <li>Select <strong>"Install app"</strong> or <strong>"Add to Home screen"</strong></li>
            <li>Confirm by tapping <strong>"Install"</strong></li>
          </ol>
        `;
        break;
      case "safari":
        steps = `
          <ol>
            <li>Tap the <strong>Share</strong> button <i class="fas fa-share-square"></i> at the bottom</li>
            <li>Scroll down and select <strong>"Add to Home Screen"</strong></li>
            <li>Tap <strong>"Add"</strong> in the top right</li>
          </ol>
        `;
        break;
      default:
        steps = `
          <ol>
            <li>Look for the <strong>Install</strong> or <strong>Add to Home Screen</strong> option in your browser menu</li>
            <li>Follow your browser's prompts to install the app</li>
          </ol>
        `;
    }

    instructions.querySelector("ol").outerHTML = steps;
    showInstructions();
  }

  // Try to trigger installation directly
  function triggerInstallation() {
    // Method 1: Use beforeinstallprompt if available
    if (deferredPrompt) {
      deferredPrompt.prompt();
      return deferredPrompt.userChoice.then((choiceResult) => {
        if (choiceResult.outcome === "accepted") {
          console.log("User accepted the install prompt");
          localStorage.setItem("pwaInstalled", "true");
          dismissPopup();
          return true;
        }
        return false;
      });
    }

    return Promise.resolve(false);
  }

  // Handle install button click
  async function handleInstallClick() {
    if (isInstalling) return;

    setInstallingState(true);

    try {
      // First try to trigger automatic installation
      const installed = await triggerInstallation();

      if (!installed) {
        // If automatic installation didn't work, show browser-specific instructions
        showBrowserSpecificInstructions();
      }
    } catch (error) {
      console.error("Installation error:", error);
      showBrowserSpecificInstructions();
    } finally {
      setInstallingState(false);
    }
  }

  // Event listeners for beforeinstallprompt event
  window.addEventListener("beforeinstallprompt", (e) => {
    console.log("beforeinstallprompt event fired");
    e.preventDefault();
    deferredPrompt = e;

    // Update button text to indicate automatic installation is available
    btnText.textContent = "Install App";
    
    // Show popup when installation is available
    if (isMobileScreen() && !checkPWAInstallation()) {
      showPopup();
    }
  });

  // Event listeners for appinstalled event
  window.addEventListener("appinstalled", (e) => {
    console.log("PWA was installed");
    isPWAInstalled = true;
    localStorage.setItem("pwaInstalled", "true");
    dismissPopup();
  });

  // Event listeners
  pwaCloseBtn.addEventListener("click", dismissPopup);
  pwaLaterBtn.addEventListener("click", dismissPopup);
  pwaInstallBtn.addEventListener("click", handleInstallClick);
  pwaPopupOverlay.addEventListener("click", function () {
    hidePopup();
    hideInstructions();
  });
  pwaInstructionsClose.addEventListener("click", function () {
    hideInstructions();
    dismissPopup();
  });

  // Service Worker Registration
  if ("serviceWorker" in navigator) {
    window.addEventListener("load", function () {
      navigator.serviceWorker
        .register("/static/sw.js")
        .then(function (registration) {
          console.log("ServiceWorker registered:", registration);
        })
        .catch(function (error) {
          console.log("ServiceWorker registration failed:", error);
        });
    });
  }

  // Show popup on page load if not installed
  if (!checkPWAInstallation()) {
    showPopup();
  }

  // Handle window resize
  window.addEventListener("resize", function () {
    if (
      isMobileScreen() &&
      !pwaInstallPopup.classList.contains("show") &&
      !checkPWAInstallation()
    ) {
      showPopup();
    } else if (!isMobileScreen()) {
      hidePopup();
    }
  });
});