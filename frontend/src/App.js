import React, { useState } from 'react';

function App() {
    const [archivo, setArchivo] = useState(null);
    const [resultado, setResultado] = useState(null);
    const [cargando, setCargando] = useState(false);
    const [error, setError] = useState(null);

    const alCambiarArchivo = (e) => {
        setArchivo(e.target.files[0]);
        setError(null);
    };

    const enviarCedula = async (e) => {
        e.preventDefault();
        if (!archivo) {
            setError("Por favor, selecciona un archivo primero.");
            return;
        }

        setCargando(true);
        setResultado(null);
        setError(null);

        const formData = new FormData();
        formData.append("file", archivo);

        try {
            // Apuntamos al puerto 8000 donde corre FastAPI
            const respuesta = await fetch("http://localhost:8000/api/v1/procesar-cedula", {
                method: "POST",
                body: formData,
            });

            const datos = await respuesta.json();

            if (!respuesta.ok) {
                throw new Error(datos.detail || "Error al procesar el documento");
            }

            setResultado(datos);
        } catch (err) {
            setError(err.message);
        } finally {
            setCargando(false);
        }
    };

    return (
        <div style={{ padding: '40px', fontFamily: 'Arial, sans-serif', maxWidth: '600px', margin: '0 auto' }}>
            <header>
                <h1 style={{ borderBottom: '2px solid #333', paddingBottom: '10px' }}>
                    Sistema de Gestión Documental - MVP Listo
                </h1>
            </header>

            <main style={{ marginTop: '20px' }}>
                <p>Sube la imagen o PDF de la cédula del ciudadano para extraer los datos mediante IA.</p>

                <form onSubmit={enviarCedula} style={{ background: '#f9f9f9', padding: '20px', borderRadius: '8px', border: '1px solid #ddd' }}>
                    <div style={{ marginBottom: '15px' }}>
                        <input
                            type="file"
                            accept="image/*,application/pdf"
                            onChange={alCambiarArchivo}
                            style={{ display: 'block', width: '100%' }}
                        />
                    </div>

                    <button
                        type="submit"
                        disabled={cargando}
                        style={{
                            background: cargando ? '#ccc' : '#007bff',
                            color: '#fff',
                            border: 'none',
                            padding: '10px 15px',
                            borderRadius: '5px',
                            cursor: cargando ? 'not-allowed' : 'pointer',
                            width: '100%',
                            fontSize: '16px'
                        }}
                    >
                        {cargando ? 'Procesando con Gemini...' : 'Procesar Cédula'}
                    </button>
                </form>

                {error && (
                    <div style={{ marginTop: '20px', padding: '10px', background: '#f8d7da', color: '#721c24', borderRadius: '5px', border: '1px solid #f5c6cb' }}>
                        <strong>Error:</strong> {error}
                    </div>
                )}

                {resultado && (
                    <div style={{ marginTop: '25px', background: '#e2f0d9', padding: '20px', borderRadius: '8px', border: '1px solid #bcd8a7' }}>
                        <h3 style={{ marginTop: 0, color: '#2b5115' }}>¡Datos Extraídos y Guardados!</h3>
                        <p><strong>Estado:</strong> {resultado.status}</p>
                        <pre style={{ background: '#fff', padding: '10px', borderRadius: '5px', overflowX: 'auto', border: '1px solid #cbd5e1' }}>
                            {JSON.stringify(resultado.data, null, 2)}
                        </pre>
                    </div>
                )}
            </main>
        </div>
    );
}

export default App;