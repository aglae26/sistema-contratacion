import React from 'react';
import ReactDOM from 'react-dom/client';
import App from './App'; // <-- Importamos tu componente con el formulario

const root = ReactDOM.createRoot(document.getElementById('root'));
root.render(
    <React.StrictMode>
        <App /> {/* <-- Renderizamos el componente dinámico */}
    </React.StrictMode>
);