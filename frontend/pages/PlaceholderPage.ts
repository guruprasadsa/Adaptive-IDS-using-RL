export const renderPlaceholderPage = (title: string): HTMLElement => {
    const main = document.createElement('main');
    main.className = 'main-content';
    main.innerHTML = `
        <div class="card placeholder-content">
            <div>
                <h2>${title}</h2>
                <p>This section is under construction.</p>
            </div>
        </div>
    `;
    return main;
};
