let tg = window.Telegram.WebApp;
tg.expand();

// Asosiy ranglarni sozlash
document.documentElement.style.setProperty('--tg-theme-bg-color', tg.backgroundColor || '#0f172a');
document.documentElement.style.setProperty('--tg-theme-text-color', tg.textColor || '#ffffff');
document.documentElement.style.setProperty('--tg-theme-button-color', tg.buttonColor || '#3b82f6');
document.documentElement.style.setProperty('--tg-theme-button-text-color', tg.buttonTextColor || '#ffffff');

const ADMIN_ID = 8006455257;

// Sahifa yuklanganda ishga tushadi
document.addEventListener('DOMContentLoaded', async () => {
    let user = tg.initDataUnsafe?.user;
    if (user) {
        document.getElementById('greeting').textContent = `Salom, ${user.first_name}! 👋`;
        
        // Agar Admin kirgan bo'lsa
        if (user.id === ADMIN_ID || user.id == ADMIN_ID) {
            document.getElementById('user-view').style.display = 'none';
            document.getElementById('admin-view').style.display = 'block';
            
            // Backend dan ma'lumot olish
            try {
                const response = await fetch(`/api/stats?user_id=${user.id}`);
                const data = await response.json();
                
                if (data.count !== undefined) {
                    document.getElementById('total-users').textContent = data.count;
                    
                    const tbody = document.querySelector('#users-table tbody');
                    tbody.innerHTML = '';
                    
                    data.users.forEach(u => {
                        const tr = document.createElement('tr');
                        // Sanani chiroyli qilish
                        const date = new Date(u.date);
                        const formattedDate = date.toLocaleDateString('uz-UZ') + " " + date.toLocaleTimeString('uz-UZ', {hour: '2-digit', minute:'2-digit'});
                        
                        tr.innerHTML = `
                            <td><code>${u.id}</code></td>
                            <td><b>${u.name}</b></td>
                            <td class="date-col">${formattedDate}</td>
                        `;
                        tbody.appendChild(tr);
                    });
                }
            } catch (err) {
                console.error("Xato:", err);
                document.getElementById('total-users').textContent = "Xato";
            }
        }
    }
});

// Botga xabar yuborish (user view uchun)
function sendMessage(text) {
    tg.sendData(text);
}

// Ilovani yopish
function closeApp() {
    tg.close();
}
