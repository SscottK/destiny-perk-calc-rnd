document.addEventListener('DOMContentLoaded', function() {
    // Initialize Bootstrap tabs
    var tabElements = document.querySelectorAll('[data-bs-toggle="tab"]');
    tabElements.forEach(function(tabElement) {
        new bootstrap.Tab(tabElement);
    });

    // Initialize filters
    initializeFilters();
    
    // Load weapons data
    loadWeapons();
    
    // Load duplicate weapons
    loadDuplicateWeapons();
});

function loadDuplicateWeapons() {
    fetch('/duplicates')
        .then(response => response.json())
        .then(data => {
            const container = document.getElementById('duplicates-container');
            container.innerHTML = '';
            
            data.forEach(weapon => {
                const row = document.createElement('tr');
                row.innerHTML = `
                    <td class="weapon-name-cell">
                        <div class="d-flex align-items-center">
                            <img src="${weapon.icon_url}" class="weapon-icon" alt="${weapon.name}" onerror="this.src='data:image/gif;base64,R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7'">
                            <span>${weapon.name}</span>
                        </div>
                    </td>
                    <td class="weapon-type-cell">${weapon.type || ''}</td>
                    <td class="damage-type-cell">
                        <span class="damage-type ${weapon.damage_type}">${weapon.damage_type || ''}</span>
                    </td>
                    <td class="season-cell">
                        <span class="season-badge">Season ${weapon.season || 'Unknown'}</span>
                    </td>
                    <td>
                        <button class="btn btn-primary btn-sm" onclick="showWeaponDetails('${weapon.hash}')">
                            View Details
                        </button>
                    </td>
                `;
                container.appendChild(row);
            });
        })
        .catch(error => {
            console.error('Error loading duplicate weapons:', error);
        });
} 