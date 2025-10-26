import { createEmptyState } from "../components/EmptyState";

export const renderPlaceholderPage = (title: string): HTMLElement => {
    const main = document.createElement('main');
    main.className = 'main-content';
    
    const card = document.createElement('div');
    card.className = 'card full-height-card';
    
    const emptyState = createEmptyState({
        icon: 'construction',
        title: `${title} Coming Soon`,
        description: 'This section is currently under development. Check back soon for updates!'
    });
    
    card.appendChild(emptyState);
    main.appendChild(card);
    
    return main;
};
