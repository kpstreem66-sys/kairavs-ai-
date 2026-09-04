async function loadProviders() {
  const response = await fetch('/api/providers');
  const data = await response.json();
  const rows = document.getElementById('provider-table');
  const select = document.getElementById('fast-teacher');
  rows.innerHTML = '';
  select.innerHTML = '';

  const providers = data.providers || [];
  for (const provider of providers) {
    const row = document.createElement('tr');
    row.innerHTML = `
      <td>${provider.name}</td>
      <td>${provider.provider_type}</td>
      <td>${provider.model || '-'}</td>
      <td>${provider.conversation_enabled ? 'Yes' : 'No'}</td>
      <td>${provider.fast_learning_enabled ? 'Yes' : 'No'}</td>
    `;
    rows.appendChild(row);

    const option = document.createElement('option');
    option.value = provider.name;
    option.textContent = provider.name;
    select.appendChild(option);
  }
}

async function saveProvider(event) {
  event.preventDefault();
  const payload = {
    name: document.getElementById('name').value,
    provider_type: document.getElementById('provider_type').value,
    base_url: document.getElementById('base_url').value,
    api_key: document.getElementById('api_key').value,
    model: document.getElementById('model').value,
    conversation_enabled: document.getElementById('conversation_enabled').checked,
    fast_learning_enabled: document.getElementById('fast_learning_enabled').checked,
  };

  const result = await fetch('/api/providers', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  const data = await result.json();
  alert(data.message || 'Provider saved.');
  loadProviders();
}

async function testProvider() {
  const payload = {
    name: document.getElementById('name').value,
    provider_type: document.getElementById('provider_type').value,
    base_url: document.getElementById('base_url').value,
    api_key: document.getElementById('api_key').value,
    model: document.getElementById('model').value,
  };

  const response = await fetch('/api/providers/test', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  const data = await response.json();
  alert(data.message || 'Test result.');
}

async function runFastLearning() {
  const providerName = document.getElementById('fast-teacher').value;
  const response = await fetch('/api/fast-learning', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ provider_name: providerName }),
  });
  const data = await response.json();
  const box = document.getElementById('fast-status');
  box.textContent = data.message || 'Fast Learning result';
}

async function saveLearnFact() {
  const message = document.getElementById('learn-message').value;
  const response = await fetch('/api/conversation-learning', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ message }),
  });
  const data = await response.json();
  const box = document.getElementById('learn-status');
  box.textContent = data.message || 'Learning result';
}

document.getElementById('provider-form').addEventListener('submit', saveProvider);
document.getElementById('test-provider').addEventListener('click', testProvider);
document.getElementById('run-fast-learning').addEventListener('click', runFastLearning);
document.getElementById('save-learn').addEventListener('click', saveLearnFact);
loadProviders();
