let tg = window.Telegram.WebApp;
tg.expand();

// Asosiy ranglarni sozlash
document.documentElement.style.setProperty('--tg-theme-bg-color', tg.backgroundColor || '#0f172a');
document.documentElement.style.setProperty('--tg-theme-text-color', tg.textColor || '#ffffff');
document.documentElement.style.setProperty('--tg-theme-button-color', tg.buttonColor || '#3b82f6');
document.documentElement.style.setProperty('--tg-theme-button-text-color', tg.buttonTextColor || '#ffffff');

// Sahifa yuklanganda ishga tushadi
document.addEventListener('DOMContentLoaded', async () => {
    let user = tg.initDataUnsafe?.user;
    if (user) {
        document.getElementById('greeting').textContent = `Salom, ${user.first_name}! 👋`;
        
        // Backend dan ma'lumot olish orqali admin ekanligini tekshiramiz
        try {
            const response = await fetch(`/api/stats?user_id=${user.id}`);
            
            // Agar 200 OK kelsa, demak u Admin!
            if (response.ok) {
                const data = await response.json();
                
                document.getElementById('user-view').style.display = 'none';
                document.getElementById('admin-view').style.display = 'block';
                
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
            } else {
                // Oddiy foydalanuvchi - hechnarsa o'zgartirmaymiz (user-view ochiq qoladi)
                console.log("Oddiy foydalanuvchi rejimi");
            }
        } catch (err) {
            console.error("Server bilan bog'lanishda xato:", err);
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

