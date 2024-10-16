document.addEventListener('DOMContentLoaded', function() {
    const generateForm = document.getElementById('generateForm');
    const downloadForm = document.getElementById('downloadForm');
    const startDateInput = document.getElementById('startDate');
    const endDateInput = document.getElementById('endDate');
    const reportDateInput = document.getElementById('reportDate');
    const loadingOverlay = document.getElementById('loadingOverlay');
    const completionModal = document.getElementById('completionModal');
    const completionMessage = document.getElementById('completionMessage');
    const closeModalButton = document.getElementById('closeModal');

    // Set max date to today for all date inputs
    const today = new Date().toISOString().split('T')[0];
    [startDateInput, endDateInput, reportDateInput].forEach(input => {
        input.setAttribute('max', today);
    });

    generateForm.addEventListener('submit', async function(e) {
        e.preventDefault();
        const startDate = startDateInput.value;
        const endDate = endDateInput.value;

        loadingOverlay.style.display = 'flex';

        try {
            const response = await fetch(`/api/v1/reports/generate-integrated-report?start_date=${startDate}&end_date=${endDate}`, {
                method: 'GET',
            });

            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }

            const result = await response.json();
            completionMessage.textContent = `Report generated successfully. File path: ${result.file_path}`;
            completionModal.style.display = 'block';
        } catch (error) {
            console.error('Report generation failed:', error);
            completionMessage.textContent = 'Report generation failed. Please check the console for more details.';
            completionModal.style.display = 'block';
        } finally {
            loadingOverlay.style.display = 'none';
        }
    });

    downloadForm.addEventListener('submit', async function(e) {
        e.preventDefault();
        const date = reportDateInput.value;

        try {
            const response = await fetch(`/api/v1/reports/download-report?date=${date}`, {
                method: 'GET',
            });

            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }

            const blob = await response.blob();
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.style.display = 'none';
            a.href = url;
            a.download = `report_${date}.zip`;
            document.body.appendChild(a);
            a.click();
            window.URL.revokeObjectURL(url);
        } catch (error) {
            console.error('Download failed:', error);
            alert('Download failed. Please check the console for more details.');
        }
    });

    closeModalButton.addEventListener('click', function() {
        completionModal.style.display = 'none';
    });

    // Set copyright year
    document.getElementById('copyright-year').textContent = new Date().getFullYear();
});