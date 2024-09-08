async function loadInstanceList() {
    try {
        const response = await fetch('/api/v1/instance_setup/list_slow_instances/');
        if (!response.ok) {
            throw new Error('Failed to load Slow MySQL Instance data.');
        }
        const data = await response.json();

        const tableBody = document.getElementById('instanceTable').getElementsByTagName('tbody')[0];
        tableBody.innerHTML = '';

        data.forEach(instance => {
            const row = tableBody.insertRow();
            row.insertCell().textContent = instance.environment;
            row.insertCell().textContent = instance.db_type;
            row.insertCell().textContent = instance.region;
            row.insertCell().textContent = instance.cluster_name || '';
            row.insertCell().textContent = instance.instance_name;
            row.insertCell().textContent = instance.host;
            row.insertCell().textContent = instance.port;

            const deleteCell = row.insertCell();
            const deleteButton = document.createElement('button');
            deleteButton.textContent = 'Delete';
            deleteButton.onclick = () => deleteInstance(instance.instance_name);
            deleteButton.className = 'delete-button';
            deleteCell.appendChild(deleteButton);
        });
    } catch (error) {
        console.error('Error:', error);
        alert('Error loading Slow MySQL Instance list: ' + error.message);
    }
}

async function deleteInstance(instanceName) {
    if (!confirm('Are you sure you want to delete this Slow MySQL Instance?')) return;

    try {
        const response = await fetch(`/api/v1/instance_setup/delete_slow_instance/?instance_name=${encodeURIComponent(instanceName)}`, {
            method: 'DELETE'
        });
        if (!response.ok) {
            throw new Error('Failed to delete Slow MySQL Instance.');
        }
        const data = await response.json();
        alert(data.message);
        await loadInstanceList();
    } catch (error) {
        console.error('Error:', error);
        alert('Error: ' + error.message);
    }
}

document.getElementById('slowMySQLForm').onsubmit = async (e) => {
    e.preventDefault();

    const formData = new FormData(e.target);
    const formProps = Object.fromEntries(formData);

    try {
        const response = await fetch('/api/v1/instance_setup/add_slow_instance/', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(formProps)
        });
        if (!response.ok) {
            throw new Error('Failed to add Slow MySQL Instance.');
        }
        const data = await response.json();
        alert(data.message);
        await loadInstanceList();
        e.target.reset();  // Reset the form
    } catch (error) {
        console.error('Error:', error);
        alert('Error: ' + error.message);
    }
};

window.onload = loadInstanceList;