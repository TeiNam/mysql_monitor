document.addEventListener('DOMContentLoaded', function() {
    const explainForm = document.getElementById('explainForm');
    const savePlanBtn = document.getElementById('savePlanBtn');
    const downloadBtn = document.getElementById('downloadBtn');

    explainForm.onsubmit = async (e) => {
        e.preventDefault();
        const pid = document.getElementById('pid').value;

        try {
            const response = await fetch('/api/v1/explain/explain', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ pid: parseInt(pid) })
            });

            if (!response.ok) {
                throw new Error('Failed to save SQL plan.');
            }

            const data = await response.json();
            alert(data.message);
        } catch (error) {
            console.error('Error:', error);
            alert('Error: ' + error.message);
        }
    };

    downloadBtn.onclick = async () => {
        const pid = document.getElementById('pid').value;

        try {
            const response = await fetch(`/api/v1/explain/download?pid=${pid}`);

            if (!response.ok) {
                throw new Error('Failed to download SQL plan.');
            }

            const blob = await response.blob();
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.style.display = 'none';
            a.href = url;
            a.download = `slowlog_pid_${pid}.md`;
            document.body.appendChild(a);
            a.click();
            window.URL.revokeObjectURL(url);
            alert('SQL plan downloaded successfully.');
        } catch (error) {
            console.error('Error:', error);
            alert('Error: ' + error.message);
        }
    };

    // Update copyright year
    document.getElementById('copyright-year').textContent = new Date().getFullYear();
});