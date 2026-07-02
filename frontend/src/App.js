import React, { useState, useEffect } from 'react';

function App() {
    // --- ESTADOS DEL MÓDULO 1: SUBIDA Y OCR ---
    const [archivo, setArchivo] = useState(null);
    const [procesandoOCR, setProcesandoOCR] = useState(false);
    const [resultadoOCR, setResultadoOCR] = useState(null);

    // --- ESTADOS DEL MÓDULO 2: TABLA DE CONTROL ---
    const [empleados, setEmpleados] = useState([]);
    const [paginaActual, setPaginaActual] = useState(1);
    const [empleadoSeleccionado, setEmpleadoSeleccionado] = useState(null);
    const [cargandoContrato, setCargandoContrato] = useState(false);

    // Campos del Formulario Unificado (Datos IA + Datos Manuales)
    const [formulario, setFormulario] = useState({
        nombres: '', apellidos: '', tipo_documento: '', numero_documento: '',
        fecha_nacimiento: '', lugar_expedicion: '', direccion_residencia: '', telefono: '',
        cargo: '', salario: '', fecha_ingreso: ''
    });

    const empleadosPorPagina = 5;

    // 1. Cargar la lista global de empleados desde PostgreSQL
    const obtenerEmpleados = async () => {
        try {
            const res = await fetch('http://localhost:8000/api/v1/empleados');
            if (res.ok) {
                const data = await res.json();
                setEmpleados(data);
            }
        } catch (err) {
            console.error("Error al conectar con la base de datos:", err);
        }
    };

    useEffect(() => {
        obtenerEmpleados();
    }, []);

    // 2. Manejar la acción de subir el documento a la IA
    const manejarEnvioOCR = async (e) => {
        e.preventDefault();
        if (!archivo) return alert("Por favor selecciona un archivo primero.");

        setProcesandoOCR(true);
        setResultadoOCR(null);

        const formData = new FormData();
        formData.append("file", archivo);

        try {
            const res = await fetch("http://localhost:8000/api/v1/procesar-cedula", {
                method: "POST",
                body: formData,
            });
            const data = await res.json();

            if (res.ok && data.status === "success") {
                setResultadoOCR("¡Documento analizado y registrado como borrador exitosamente!");
                setArchivo(null);
                obtenerEmpleados(); // Refrescar la tabla en tiempo real
            } else {
                alert(`Error: ${data.detail || "No se pudo procesar el archivo"}`);
            }
        } catch (err) {
            alert("Error de conexión con el servidor backend.");
        } finally {
            setProcesandoOCR(false);
        }
    };

    // 3. Lógica de cálculo para la paginación
    const indiceUltimo = paginaActual * empleadosPorPagina;
    const indicePrimero = indiceUltimo - empleadosPorPagina;
    const empleadosPaginados = empleados.slice(indicePrimero, indiceUltimo);
    const totalPaginas = Math.ceil(empleados.length / empleadosPorPagina);

    // 4. Desplegar el modal inyectando lo que capturó previamente la IA
    const abrirModalEdicion = (emp) => {
        setEmpleadoSeleccionado(emp);
        setFormulario({
            nombres: emp.nombres || '',
            apellidos: emp.apellidos || '',
            tipo_documento: emp.tipo_documento || '',
            numero_documento: emp.numero_documento || '',
            fecha_nacimiento: emp.fecha_nacimiento || '',
            lugar_expedicion: emp.lugar_expedicion || '',
            direccion_residencia: emp.direccion_residencia || '',
            telefono: emp.telefono || '',
            cargo: '', // Nace vacío para digitación obligatoria manual
            salario: '', // Nace vacío para digitación obligatoria manual
            fecha_ingreso: new Date().toISOString().split('T')[0] // Sugiere la fecha de hoy
        });
    };

    // 5. Despachar aprobación final y disparar la creación de la plantilla de Google Docs
    const manejarAprobacionContrato = async (e) => {
        e.preventDefault();
        setCargandoContrato(true);
        try {
            const res = await fetch(`http://localhost:8000/api/v1/empleados/${empleadoSeleccionado.id}/aprobar`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(formulario)
            });
            const resultado = await res.json();

            if (res.ok && resultado.status === 'success') {
                alert("¡Candidato aprobado! Contrato inyectado y organizado en Google Drive.");
                if (resultado.contrato_url) {
                    window.open(resultado.contrato_url, '_blank'); // Abre el Google Doc generado de inmediato
                }
                setEmpleadoSeleccionado(null); // Cerrar ventana flotante
                obtenerEmpleados(); // Actualizar estados de la tabla
            } else {
                alert("Ocurrió un inconveniente al procesar la firma del contrato.");
            }
        } catch (err) {
            alert("Error de comunicación HTTP con el servicio de contratación.");
        } finally {
            setCargandoContrato(false);
        }
    };

    return (
        <div style={{ maxWidth: '1000px', margin: '0 auto', padding: '30px', fontFamily: 'Arial, sans-serif', color: '#333' }}>
            <header style={{ borderBottom: '2px solid #eaeaea', paddingBottom: '15px', marginBottom: '30px' }}>
                <h1 style={{ margin: 0, fontSize: '28px' }}>🚀 Sistema Inteligente de Gestión Documental y Contratación</h1>
                {/*<p style={{ color: '#666', marginTop: '5px' }}></p>*/}
            </header>

            {/* SECCIÓN 1: MOTOR DE INGESTA OCR */}
            <section style={{ backgroundColor: '#f9f9f9', padding: '20px', borderRadius: '8px', border: '1px solid #e1e1e1', marginBottom: '40px' }}>
                <h3 style={{ marginTop: 0 }}>📂 Nuevos Candidatos</h3>
                <p style={{ fontSize: '14px', color: '#555' }}>Sube el PDF, JPEG o PNG del documento de identidad.</p>

                <form onSubmit={manejarEnvioOCR} style={{ display: 'flex', gap: '15px', alignItems: 'center', marginTop: '15px' }}>
                    <input
                        type="file"
                        accept="image/jpeg,image/png,application/pdf"
                        onChange={(e) => setArchivo(e.target.files[0])}
                        style={{ padding: '8px', border: '1px dashed #ccc', borderRadius: '4px', backgroundColor: '#fff' }}
                    />
                    <button
                        type="submit"
                        disabled={procesandoOCR}
                        style={{ backgroundColor: '#007bff', color: '#fff', border: 'none', padding: '10px 20px', borderRadius: '4px', fontWeight: 'bold', cursor: 'pointer', opacity: procesandoOCR ? 0.6 : 1 }}
                    >
                        {procesandoOCR ? "Analizando Cédula con IA..." : "Escanear y Registrar"}
                    </button>
                </form>

                {resultadoOCR && (
                    <div style={{ marginTop: '15px', padding: '10px 15px', backgroundColor: '#e8f5e9', color: '#2e7d32', borderRadius: '4px', fontWeight: '500', fontSize: '14px' }}>
                        {resultadoOCR}
                    </div>
                )}
            </section>

            {/* SECCIÓN 2: PANEL DE CONTROL Y CONTROL DE ESTADOS */}
            <section>
                <h3 style={{ marginBottom: '15px' }}>📋 Consola de Gestión Humana</h3>

                <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left', boxShadow: '0 2px 5px rgba(0,0,0,0.05)' }}>
                    <thead>
                        <tr style={{ backgroundColor: '#4a5568', color: '#fff' }}>
                            <th style={{ padding: '12px' }}>Documento Identidad</th>
                            <th style={{ padding: '12px' }}>Candidato</th>
                            <th style={{ padding: '12px' }}>Estado Operativo</th>
                            <th style={{ padding: '12px' }}>Fases Contractuales</th>
                        </tr>
                    </thead>
                    <tbody>
                        {empleadosPaginados.map(emp => (
                            <tr key={emp.id} style={{ borderBottom: '1px solid #e2e8f0' }}>
                                <td style={{ padding: '12px' }}><strong>{emp.numero_documento}</strong> <span style={{ fontSize: '11px', color: '#718096' }}>({emp.tipo_documento})</span></td>
                                <td style={{ padding: '12px' }}>{emp.nombres} {emp.apellidos}</td>
                                <td style={{ padding: '12px' }}>
                                    <span style={{
                                        padding: '4px 8px', borderRadius: '12px', fontWeight: 'bold', fontSize: '11px',
                                        backgroundColor: emp.estado === 'REGISTRADO' ? '#feeb8c' : '#c6f6d5',
                                        color: emp.estado === 'REGISTRADO' ? '#744210' : '#22543d'
                                    }}>
                                        {emp.estado}
                                    </span>
                                </td>
                                <td style={{ padding: '12px' }}>
                                    <button
                                        onClick={() => abrirModalEdicion(emp)}
                                        style={{ backgroundColor: emp.estado === 'REGISTRADO' ? '#3182ce' : '#718096', color: '#fff', border: 'none', padding: '6px 12px', borderRadius: '4px', cursor: 'pointer', fontWeight: '500' }}
                                    >
                                        {emp.estado === 'REGISTRADO' ? 'Validar y Contratar' : 'Ver Ficha Completa'}
                                    </button>
                                </td>
                            </tr>
                        ))}
                        {empleados.length === 0 && (
                            <tr>
                                <td colSpan="4" style={{ padding: '20px', textAlign: 'center', color: '#a0aec0' }}>No hay registros en la base de datos. Ingiere una cédula arriba.</td>
                            </tr>
                        )}
                    </tbody>
                </table>

                {/* PAGINADOR DINÁMICO */}
                <div style={{ marginTop: '20px', display: 'flex', gap: '10px', alignItems: 'center', justifyContent: 'center' }}>
                    <button disabled={paginaActual === 1} onClick={() => setPaginaActual(p => p - 1)} style={{ padding: '5px 10px', cursor: 'pointer' }}>Anterior</button>
                    <span style={{ fontSize: '14px', color: '#4a5568' }}>Página <strong>{paginaActual}</strong> de {totalPaginas || 1}</span>
                    <button disabled={paginaActual === totalPaginas || totalPaginas === 0} onClick={() => setPaginaActual(p => p + 1)} style={{ padding: '5px 10px', cursor: 'pointer' }}>Siguiente</button>
                </div>
            </section>

            {/* SECCIÓN 3: FORMULARIO INTERACTIVO (VENTANA MODAL FLOTANTE) */}
            {empleadoSeleccionado && (
                <div style={{
                    position: 'fixed', top: 0, left: 0, width: '100%', height: '100%',
                    backgroundColor: 'rgba(0,0,0,0.4)', display: 'flex', justifyContent: 'center', alignItems: 'center', zIndex: 9999
                }}>
                    <div style={{ backgroundColor: '#fff', padding: '30px', borderRadius: '8px', width: '520px', maxHeight: '85vh', overflowY: 'auto', boxShadow: '0 10px 25px rgba(0,0,0,0.15)' }}>
                        <h3 style={{ marginTop: 0, color: '#2d3748' }}>🛠️ Auditoría de Datos y Minuta de Contrato</h3>
                        <p style={{ color: '#718096', fontSize: '13px', marginBottom: '20px' }}>Verifica que los datos del escaneo de la IA sean correctos y complementa con la información contractual.</p>

                        <form onSubmit={manejarAprobacionContrato}>
                            <h4 style={{ color: '#4a5568', marginBottom: '10px', borderBottom: '1px solid #edf2f7', paddingBottom: '5px' }}>1. Verificación del Documento de Identidad</h4>

                            <label style={{ fontSize: '12px', fontWeight: 'bold', color: '#4a5568' }}>Nombres Completos:</label>
                            <input type="text" value={formulario.nombres} onChange={e => setFormulario({ ...formulario, nombres: e.target.value })} required style={{ width: '100%', padding: '8px', margin: '6px 0 12px 0', borderRadius: '4px', border: '1px solid #cbd5e0' }} />

                            <label style={{ fontSize: '12px', fontWeight: 'bold', color: '#4a5568' }}>Apellidos Completos:</label>
                            <input type="text" value={formulario.apellidos} onChange={e => setFormulario({ ...formulario, apellidos: e.target.value })} required style={{ width: '100%', padding: '8px', margin: '6px 0 12px 0', borderRadius: '4px', border: '1px solid #cbd5e0' }} />

                            <div style={{ display: 'flex', gap: '10px' }}>
                                <div style={{ flex: 1 }}>
                                    <label style={{ fontSize: '12px', fontWeight: 'bold', color: '#4a5568' }}>Tipo Documento:</label>
                                    <input type="text" value={formulario.tipo_documento} onChange={e => setFormulario({ ...formulario, tipo_documento: e.target.value })} required style={{ width: '100%', padding: '8px', margin: '6px 0 12px 0', borderRadius: '4px', border: '1px solid #cbd5e0' }} />
                                </div>
                                <div style={{ flex: 1 }}>
                                    <label style={{ fontSize: '12px', fontWeight: 'bold', color: '#4a5568' }}>Número:</label>
                                    <input type="text" value={formulario.numero_documento} onChange={e => setFormulario({ ...formulario, numero_documento: e.target.value })} required style={{ width: '100%', padding: '8px', margin: '6px 0 12px 0', borderRadius: '4px', border: '1px solid #cbd5e0' }} />
                                </div>
                            </div>

                            <label style={{ fontSize: '12px', fontWeight: 'bold', color: '#4a5568' }}>Dirección de Residencia:</label>
                            <input type="text" value={formulario.direccion_residencia} onChange={e => setFormulario({ ...formulario, direccion_residencia: e.target.value })} placeholder="Ej: Avenida 15 # 103-24" style={{ width: '100%', padding: '8px', margin: '6px 0 12px 0', borderRadius: '4px', border: '1px solid #cbd5e0' }} />

                            <label style={{ fontSize: '12px', fontWeight: 'bold', color: '#4a5568' }}>Teléfono Celular:</label>
                            <input type="text" value={formulario.telefono} onChange={e => setFormulario({ ...formulario, telefono: e.target.value })} placeholder="Ej: 3124567890" style={{ width: '100%', padding: '8px', margin: '6px 0 12px 0', borderRadius: '4px', border: '1px solid #cbd5e0' }} />

                            <h4 style={{ color: '#4a5568', marginTop: '20px', marginBottom: '10px', borderBottom: '1px solid #edf2f7', paddingBottom: '5px' }}>2. Cláusulas y Datos de Contratación (Manual)</h4>

                            <label style={{ fontSize: '12px', fontWeight: 'bold', color: '#4a5568' }}>Cargo Estipulado:</label>
                            <input type="text" value={formulario.cargo} onChange={e => setFormulario({ ...formulario, cargo: e.target.value })} required placeholder="Ej: Ingeniero de Datos Senior" style={{ width: '100%', padding: '8px', margin: '6px 0 12px 0', borderRadius: '4px', border: '1px solid #cbd5e0' }} />

                            <label style={{ fontSize: '12px', fontWeight: 'bold', color: '#4a5568' }}>Salario Integral Mensual ($):</label>
                            <input type="text" value={formulario.salario} onChange={e => setFormulario({ ...formulario, salario: e.target.value })} required placeholder="Ej: 4.800.000" style={{ width: '100%', padding: '8px', margin: '6px 0 12px 0', borderRadius: '4px', border: '1px solid #cbd5e0' }} />

                            <label style={{ fontSize: '12px', fontWeight: 'bold', color: '#4a5568' }}>Fecha Oficial de Ingreso:</label>
                            <input type="date" value={formulario.fecha_ingreso} onChange={e => setFormulario({ ...formulario, fecha_ingreso: e.target.value })} required style={{ width: '100%', padding: '8px', margin: '6px 0 20px 0', borderRadius: '4px', border: '1px solid #cbd5e0', fontFamily: 'Arial, sans-serif' }} />

                            {/* BOTONERA ACCIONES DE CIERRE */}
                            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '12px', marginTop: '10px' }}>
                                <button type="button" onClick={() => setEmpleadoSeleccionado(null)} style={{ padding: '10px 18px', borderRadius: '4px', border: '1px solid #cbd5e0', backgroundColor: '#fff', cursor: 'pointer', fontWeight: 'bold' }}>Cerrar</button>
                                <button
                                    type="submit"
                                    disabled={cargandoContrato || empleadoSeleccionado.estado !== 'REGISTRADO'}
                                    style={{ backgroundColor: empleadoSeleccionado.estado === 'REGISTRADO' ? '#48bb78' : '#718096', color: '#fff', border: 'none', padding: '10px 20px', borderRadius: '4px', fontWeight: 'bold', cursor: 'pointer', opacity: cargandoContrato ? 0.7 : 1 }}
                                >
                                    {cargandoContrato ? 'Compilando Minuta en Drive...' : empleadoSeleccionado.estado === 'REGISTRADO' ? 'Aprobar y Crear Contrato' : 'Contrato Ya Generado'}
                                </button>
                            </div>
                        </form>
                    </div>
                </div>
            )}
        </div>
    );
}

export default App;