var loader = document.getElementById("preloader");
setTimeout(function () {
  loader.style.display = "none";
}, (timeout = 2000));

// Hamburger Menu Toggle
document.addEventListener('DOMContentLoaded', function() {
  const hamburger = document.querySelector('.hamburger');
  const navlinks = document.querySelector('.navlinks');
  
  if (hamburger) {
    hamburger.addEventListener('click', function() {
      hamburger.classList.toggle('active');
      navlinks.classList.toggle('active');
    });

    // Close menu when clicking on a link
    const navItems = document.querySelectorAll('.navlink');
    navItems.forEach(item => {
      item.addEventListener('click', function() {
        hamburger.classList.remove('active');
        navlinks.classList.remove('active');
      });
    });

    // Close menu when clicking outside
    document.addEventListener('click', function(event) {
      const isClickInsideNav = navlinks.contains(event.target);
      const isClickOnHamburger = hamburger.contains(event.target);
      
      if (!isClickInsideNav && !isClickOnHamburger && navlinks.classList.contains('active')) {
        hamburger.classList.remove('active');
        navlinks.classList.remove('active');
      }
    });
  }
});

document.getElementById("openDialogBtn").addEventListener("click", openDialog);

function openDialog() {
  document.getElementById("dialog").style.display = "block";
}

function closeDialog() {
  document.getElementById("dialog").style.display = "none";
}

document.getElementById("uploadBtn").addEventListener("click", function () {
  var fileInput = document.getElementById("fileInput");

  // Check if a file is selected
  if (fileInput.files.length > 0) {
    var selectedFile = fileInput.files[0];

    // Create a FormData object to send the file
    var formData = new FormData();
    formData.append("file", selectedFile);

    // Send a POST request to the Flask backend
    fetch("/upload", {
      method: "POST",
      body: formData,
    })
      .then((response) => response.json())
      .then((data) => {
        // Handle the response from the backend
        window.location.href = "/result?content=" + data.content;
      })
      .catch((error) => {
        console.error("Error:", error);
      });

    closeDialog(); // Optionally, close the dialog after sending the request
  } else {
    alert("Please choose a file before clicking Upload.");
  }
});

// Search list
var loader = document.getElementById("preloader");
setTimeout(function () {
  loader.style.display = "none";
}, 2000);

document.getElementById("loadingSpinner").style.display = "block";
fetch("/pill-detect", { method: "POST", body: formData })
  .then((response) => response.json())
  .then((data) => {
    document.getElementById("loadingSpinner").style.display = "none";
    // Handle the response...
  });

const searchButton = document.getElementById("searchButton");
const drugInput = document.getElementById("drugInput");
const resultsContainer = document.getElementById("results");

searchButton.addEventListener("click", handleSearch);

searchButton.addEventListener("click", function (event) {
  event.preventDefault(); // Prevent the default form submission

  const pillName = document.getElementById("drugInput").value.trim();
  if (!pillName) {
    alert("Please enter a pill name.");
    return;
  }

  // Create a form and submit it
  const form = new FormData();
  form.append("drug_name", pillName);

  fetch("/get-drug-info", {
    method: "POST",
    body: form,
  })
    .then((response) => response.text())
    .then((html) => {
      // Replace the current page with the returned HTML
      document.open();
      document.write(html);
      document.close();
    })
    .catch((error) => console.error("Error:", error));
});

// File upload functionality
const dropzone = document.getElementById("dropzone");
const fileInput = document.getElementById("fileInput");
const fileList = document.getElementById("fileList");
const filePreviews = document.getElementById("filePreviews");
const uploadButton = document.getElementById("uploadButton");
const clearButton = document.getElementById("clearButton");
const resultContainer = document.getElementById("image-result");
const statusMessage = document.getElementById("statusMessage");

dropzone.addEventListener("click", () => fileInput.click());

fileInput.addEventListener("change", (event) =>
  handleFiles(event.target.files)
);

dropzone.addEventListener("dragover", (event) => {
  event.preventDefault();
  dropzone.classList.add("drag-over");
});

dropzone.addEventListener("dragleave", () =>
  dropzone.classList.remove("drag-over")
);

dropzone.addEventListener("drop", (event) => {
  event.preventDefault();
  dropzone.classList.remove("drag-over");
  handleFiles(event.dataTransfer.files);
});

function handleFiles(files) {
  const fileArray = Array.from(files);
  const fileItems = fileArray.map((file) => `<li>${file.name}</li>`);
  fileList.innerHTML = `<ul>${fileItems.join("")}</ul>`;

  if (fileArray.length > 0) {
    uploadButton.disabled = false;
    clearButton.disabled = false;
  } else {
    uploadButton.disabled = true;
    clearButton.disabled = true;
  }

  filePreviews.innerHTML = "";

  fileArray.forEach((file) => {
    const reader = new FileReader();
    reader.onload = (event) => {
      const result = event.target.result;
      let preview = file.type.startsWith("image/")
        ? `<img src="${result}" alt="${file.name}">`
        : `<p>Preview not available for ${file.name}</p>`;
      filePreviews.innerHTML += preview;
    };
    reader.readAsDataURL(file);
  });
}

clearButton.addEventListener("click", () => {
  fileInput.value = "";
  fileList.innerHTML = "";
  filePreviews.innerHTML = "";
  uploadButton.disabled = true;
  clearButton.disabled = true;
});

uploadButton.addEventListener("click", (event) => {
  event.preventDefault(); // Prevent form submission
  let loadingMessages = [
    "Model Loading.....",
    "Please wait, processing...",
    "Almost there...",
    "Fetching results...",
    "Hang tight...",
  ];
  let loadingIndex = 0;

  // Set an interval to update the loading message
  loadingInterval = setInterval(() => {
    statusMessage.innerText = loadingMessages[loadingIndex];
    loadingIndex = (loadingIndex + 1) % loadingMessages.length; // Cycle through messages
  }, 1000); // Change message every 1 second

  const file = fileInput.files[0]; // Get the file from the input

  if (file) {
    const formData = new FormData();
    formData.append("file", file); // Append the file to the FormData object

    // Send the file to the Flask backend
    fetch("/pill-detect", {
      method: "POST",
      body: formData,
    })
      .then((response) => {
        clearInterval(loadingInterval);
        if (!response.ok) {
          throw new Error(`HTTP error! Status: ${response.status}`);
        }
        return response.json();
      })
      .then((data) => {
        console.log("Response from server:", data); // Log the response data
        // Handle the response from the server
        if (data.error) {
          resultContainer.innerHTML = `<p class="error">${data.error}</p>`;
        } else {
          resultContainer.innerHTML = `
                    <h2>Pill Detected: ${data.pill_name}</h2>
                    <p>${data.information}</p>
                `;
        }
      })
      .catch((error) => {
        console.error("Error:", error);
        resultContainer.innerHTML = `<p class="error">Error processing request. Please try again.</p>`;
      });
  } else {
    clearInterval(loadingInterval);
    statusMessage.innerText = "Please select a file to upload.";
  }
  if (file.type.startsWith("image/") && file.size <= 5 * 1024 * 1024) {
    // Proceed with upload
  } else {
    alert(
      "Please upload a valid image file (JPEG, PNG, etc.) smaller than 5MB."
    );
  }
});

// Add this code for handling form submission
document
  .querySelector(".contact-form")
  .addEventListener("submit", function (e) {
    e.preventDefault();

    const formData = new FormData(this);

    fetch("/submit_form", {
      method: "POST",
      body: formData,
    })
      .then((response) => response.text())
      .then((data) => {
        alert(data); // Show success message
        this.reset(); // Clear the form
        window.location.reload(); // Refresh the page
      })
      .catch((error) => {
        console.error("Error:", error);
        alert("There was an error sending your message. Please try again.");
      });
  });
