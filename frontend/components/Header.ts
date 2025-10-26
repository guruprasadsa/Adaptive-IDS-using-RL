import { navItems } from '../data';
import type { User } from '../types';
import { getRoleBadgeColor, getRoleDisplayName } from '../utils/rbac';

export const renderHeader = (
    activePage: string, 
    user: User | null = null, 
    onLogout?: () => void
): HTMLElement => {
    const header = document.createElement('header');
    header.className = 'header';
    
    const userName = user?.username || 'User';
    const userRole = user?.role || 'viewer';
    const roleDisplay = getRoleDisplayName(userRole);
    const roleBadgeColor = getRoleBadgeColor(userRole);
    
    header.innerHTML = `
        <div class="header-left">
            <div class="header-logo">
                <span class="material-symbols-outlined logo">security</span>
                <h1>Adaptive IDS</h1>
            </div>
            <nav class="header-nav">
                <ul class="header-nav-list">
                    ${navItems.map(item => `
                        <li class="nav-item">
                            <a href="#${item.id}" class="nav-link ${item.id === activePage ? 'active' : ''}" data-page="${item.id}">
                                <span class="material-symbols-outlined">${item.icon}</span>
                                <span>${item.label}</span>
                            </a>
                        </li>
                    `).join('')}
                </ul>
            </nav>
        </div>
        <div class="header-actions">
            <div class="user-profile">
                <div class="user-info">
                    <span class="material-symbols-rounded user-icon"><svg xmlns="http://www.w3.org/2000/svg" x="0px" y="0px" width="30" height="30" viewBox="0,0,256,256">
<g fill="#4bd82d" fill-rule="nonzero" stroke="none" stroke-width="1" stroke-linecap="butt" stroke-linejoin="miter" stroke-miterlimit="10" stroke-dasharray="" stroke-dashoffset="0" font-family="none" font-weight="none" font-size="none" text-anchor="none" style="mix-blend-mode: normal"><g transform="scale(8.53333,8.53333)"><path d="M15,3.00195c-4.242,0 -6,2.721 -6,6c0,1.104 0.52734,2.21289 0.52734,2.21289c-0.212,0.121 -0.56066,0.50826 -0.47266,1.19726c0.164,1.283 0.72022,1.60972 1.07422,1.63672c0.135,1.197 1.42109,2.72817 1.87109,2.95117v2c-0.083,0.251 -0.23034,0.45553 -0.40234,0.64453c0.838,0.723 1.97634,1.35547 3.40234,1.35547c1.426,0 2.56434,-0.63247 3.40234,-1.35547c-0.172,-0.189 -0.31934,-0.39353 -0.40234,-0.64453v-2c0.45,-0.223 1.73609,-1.75417 1.87109,-2.95117c0.354,-0.027 0.91022,-0.35372 1.07422,-1.63672c0.088,-0.689 -0.26066,-1.07526 -0.47266,-1.19726c0,0 0.52734,-1.00189 0.52734,-2.21289c0,-2.428 -0.953,-4.5 -3,-4.5c0,0 -0.711,-1.5 -3,-1.5zM9.76172,20.67383c-2.697,0.916 -6.76172,1.33217 -6.76172,6.32617h24c0,-4.994 -4.06472,-5.41017 -6.76172,-6.32617c-1.14,1.155 -2.87428,2.32617 -5.23828,2.32617c-2.364,0 -4.09828,-1.17117 -5.23828,-2.32617z"></path></g></g>
</svg></span>
                    <div class="user-details">
                        <span class="user-name">${userName}</span>
                        <span class="user-role" style="background-color: ${roleBadgeColor}; padding: 2px 8px; border-radius: 4px; font-size: 11px; color: white;">${roleDisplay}</span>
                    </div>
                </div>
                <button class="logout-button" id="logoutButton" title="Logout">
                    <span class="material-symbols-rounded">
                    <svg xmlns="http://www.w3.org/2000/svg" x="0px" y="0px" width="24" height="24" viewBox="0 0 24 24">
<path fill="#306263" d="M21.591,11.133l-3.38-2.91c-0.48-0.48-1.21-0.12-1.21,0.47l-0.001,1.308c0,0.552-0.448,0.999-1,1h0	c-0.553,0-1.001-0.448-1.001-1V5c0-1.105-0.895-2-2-2H5C3.895,3,3,3.895,3,5v14c0,1.105,0.895,2,2,2h8c1.105,0,2-0.895,2-2v-4.997	c0-0.552,0.448-1,1-1h0.001c0.552,0,1,0.448,1,1v1.29c0,0.59,0.71,0.97,1.23,0.45l3.36-2.9	C22.151,12.393,22.121,11.563,21.591,11.133z"></path>
</svg>
                    </span>
                </button>
            </div>
        </div>
    `;
    
    // Attach logout handler
    if (onLogout) {
        const logoutButton = header.querySelector('#logoutButton');
        if (logoutButton) {
            logoutButton.addEventListener('click', (e) => {
                e.preventDefault();
                onLogout();
            });
        }
    }
    
    return header;
};