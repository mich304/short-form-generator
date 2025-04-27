const youtubeLinkInput = document.getElementById('youtubeLink');
const convertButton = document.getElementById('convertButton');
const loadingIndicator = document.getElementById('loadingIndicator');
const optionsDiv = document.getElementById('optionsDiv'); // Get the new options div
const processButton = document.getElementById('processButton'); // Get the new process button
const segmentsDiv = document.getElementById('segmentsDiv'); // Get the segments div

let progressInterval; // Variable to hold the interval ID
let segmentFilenames = []; // Variable to store segment filenames

convertButton.addEventListener('click', () => {
    const link = youtubeLinkInput.value;
    if (link) {
        console.log('Convert button clicked with link:', link);

        // Show loading indicator and disable button
        loadingIndicator.style.display = 'block';
        loadingIndicator.textContent = 'Loading... 0%'; // Initial loading text
        convertButton.disabled = true;
        segmentsDiv.innerHTML = ''; // Clear previous content immediately
        segmentsDiv.style.display = 'none'; // Hide segments div initially
        optionsDiv.style.display = 'none'; // Hide options div initially


        // Start polling for progress
        progressInterval = setInterval(fetchProgress, 1000); // Poll every 1 second

        fetch('/convert', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ youtube_link: link }),
        })
        .then(response => {
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            return response.json();
        })
        .then(data => {
            console.log('Received response:', data);

            if (data.segments && data.segments.length > 0) {
                console.log('Segments received:', data.segments);
                segmentFilenames = data.segments; // Store segment filenames
                optionsDiv.style.display = 'block'; // Show options div
            } else if (data.error) {
                 console.error('Error from server:', data.error);
                 const errorMessage = document.createElement('p');
                 errorMessage.textContent = `Error: ${data.error}`;
                 errorMessage.style.color = 'red';
                 segmentsDiv.appendChild(errorMessage);
                 segmentsDiv.style.display = 'block'; // Show segments div to display error
            }
             else {
                const p = document.createElement('p');
                p.textContent = 'No segments found or an unknown error occurred.';
                segmentsDiv.appendChild(p);
                segmentsDiv.style.display = 'block'; // Show segments div to display message
            }
        })
        .catch(error => {
            console.error('Error during conversion:', error);
            console.log('Full error object:', error);
            console.log('Error response:', error.response);
            segmentsDiv.innerHTML = '';
            const errorMessage = document.createElement('p');

            // Try to get detailed error message from response
            if (error.response && error.response.json) {
                error.response.json().then(data => {
                    errorMessage.textContent = `Server Error: ${data.error || 'Unknown error'}`;
                }).catch(() => {
                    errorMessage.textContent = `Error: ${error.message || error.statusText || String(error)}`;
                });
            } else {
                errorMessage.textContent = `Error: ${error.message || String(error)}`;
            }

            errorMessage.style.color = 'red';
            segmentsDiv.appendChild(errorMessage);
            segmentsDiv.style.display = 'block';
        })
        .finally(() => {
            // Stop polling and hide loading indicator, re-enable button
            clearInterval(progressInterval);
            loadingIndicator.style.display = 'none';
            convertButton.disabled = false;
        });
    } else {
        console.log('Please enter a YouTube link.');
        segmentsDiv.innerHTML = ''; // Clear previous content
        const message = document.createElement('p');
        message.textContent = 'Please enter a YouTube link.';
        segmentsDiv.appendChild(message);
        segmentsDiv.style.display = 'block'; // Show segments div to display message
    }
});

// Add event listener for the new process button
processButton.addEventListener('click', () => {
    const selectedOption = document.querySelector('input[name="aspectRatio"]:checked').value;
    console.log('Process button clicked with option:', selectedOption);
    console.log('Processing segments:', segmentFilenames);

    // Hide options and show loading indicator for processing
    optionsDiv.style.display = 'none';
    loadingIndicator.style.display = 'block';
    loadingIndicator.textContent = 'Processing videos...'; // Update loading text

    // Send request to backend to process videos
    fetch('/process_videos', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({ segments: segmentFilenames, option: selectedOption }),
    })
    .then(response => {
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        return response.json();
    })
    .then(data => {
        console.log('Received processed videos response:', data);
        segmentsDiv.innerHTML = ''; // Clear previous content

        if (data.processed_segments && data.processed_segments.length > 0) {
            console.log('Displaying download links for processed segments:', data.processed_segments);
            let downloadedCount = 0;
            data.processed_segments.forEach(segmentFilename => {
                const link = document.createElement('a');
                link.href = `/download_segment/${segmentFilename}`; 
                link.textContent = `Download ${segmentFilename}`;
                link.download = segmentFilename;
                link.classList.add('download-button');
                
                link.addEventListener('click', async () => {
                    await fetch(`/delete_segment/${segmentFilename}`, {
                        method: 'DELETE'
                    });
                    link.style.display = 'none';
                    downloadedCount++;
                    
                    if (downloadedCount === data.processed_segments.length) {
                        setTimeout(() => {
                            window.location.reload();
                        }, 1000);
                    }
                });
                
                segmentsDiv.appendChild(link);
            });
            segmentsDiv.style.display = 'block'; // Show segments div
            console.log('Download links for processed videos displayed on the page.');
        } else if (data.error) {
             console.error('Error during processing:', data.error);
             const errorMessage = document.createElement('p');
             errorMessage.textContent = `Error: ${data.error}`;
             errorMessage.style.color = 'red';
             segmentsDiv.appendChild(errorMessage);
             segmentsDiv.style.display = 'block'; // Show segments div to display error
        }
         else {
            const p = document.createElement('p');
            p.textContent = 'No processed segments found or an unknown error occurred.';
            segmentsDiv.appendChild(p);
            segmentsDiv.style.display = 'block'; // Show segments div to display message
        }
    })
    .catch(error => {
        console.error('Error during video processing:', error);
        segmentsDiv.innerHTML = ''; // Clear previous content
        const errorMessage = document.createElement('p');
        errorMessage.textContent = `An error occurred: ${error.message}`;
        errorMessage.style.color = 'red';
        segmentsDiv.appendChild(errorMessage);
        segmentsDiv.style.display = 'block'; // Show segments div to display error
    })
    .finally(() => {
        loadingIndicator.style.display = 'none'; // Hide loading indicator
    });
});


// Function to fetch progress from the backend
function fetchProgress() {
    fetch('/progress')
        .then(response => response.json())
        .then(data => {
            if (data.progress !== undefined) {
                loadingIndicator.textContent = `Loading... ${data.progress.toFixed(1)}%`;
            }
        })
        .catch(error => {
            console.error('Error fetching progress:', error);
            // Optionally stop polling or show an error message
        });
}