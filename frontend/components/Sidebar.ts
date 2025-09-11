import { NavItem } from '../types';
import { navItems } from '../data';

export const renderSidebar = (activePage: string): HTMLElement => {
    const sidebar = document.createElement('nav');
    sidebar.className = 'sidebar';
    sidebar.innerHTML = `
        <div class="sidebar-header">
            <span class="material-symbols-outlined logo">security</span>
            <h1>Adaptive IDS</h1>
        </div>
        <ul class="nav-list">
            ${navItems.map(item => `
                <li class="nav-item">
                    <a href="#${item.id}" class="${item.id === activePage ? 'active' : ''}" data-nav-id="${item.id}">
                        <span class="material-symbols-outlined">${item.icon}</span>
                        <span>${item.label}</span>
                    </a>
                </li>
            `).join('')}
        </ul>
    `;
    return sidebar;
};
