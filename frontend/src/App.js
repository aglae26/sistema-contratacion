import React, { useState, useEffect } from 'react';

function App() {
    // --- ESTADOS DEL MÓDULO 1: SUBIDA Y OCR ---
    const [archivo, setArchivo] = useState(null);
    const [procesandoOCR, setProcesandoOCR] = useState(false);
    const [resultadoOCR, setResultadoOCR] = useState(null);

    // --- ESTADOS DEL MÓDULO 2: PANEL DE CONTROL Y CONFIGURACIÓN ---
    const [empleados, setEmpleados] = useState([]);
    const [paginaActual, setPaginaActual] = useState(1);
    const [empleadoSeleccionado, setEmpleadoSeleccionado] = useState(null);
    const [cargandoContrato, setCargandoContrato] = useState(false);

    // 🚨 ESTADOS COMPLEMENTARIOS PARA LA ASOCIACIÓN MULTIEMPRESA 🚨
    const [sociedades, setSociedades] = useState([]); // Almacena las empresas de PostgreSQL
    const [sedesDisponibles, setSedesDisponibles] = useState([]); // Almacena las sedes filtradas

    // Campos del Formulario Unificado (Datos IA + Datos Manuales)
    const [formulario, setFormulario] = useState({
        nombres: '',
        apellidos: '',
        tipo_documento: '',
        numero_documento: '',
        fecha_nacimiento: '',
        lugar_expedicion: '',
        fecha_expedicion: '',
        direccion_residencia: '',
        telefono: '',
        empresa_id: '',
        sede_id: '',
        aplica_sede: true,
        sede_manual: '',
        tipo_contrato: 'INDEFINIDO_ESTANDAR',
        cargo: '',
        salario: '',
        fecha_ingreso: ''
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

    // 🏢 Cargar catálogo de sociedades desde el Backend
    const obtenerSociedades = async () => {
        try {
            const res = await fetch('http://localhost:8000/api/v1/sociedades');
            if (res.ok) {
                const data = await res.json();
                setSociedades(data);
            }
        } catch (err) {
            console.error("Error al conectar con el catálogo de sociedades:", err);
        }
    };

    // 📍 Cargar sedes encadenadas de forma reactiva según la empresa elegida
    const cargarSedesDeEmpresa = async (empresaId) => {
        if (!empresaId) return;
        try {
            const res = await fetch(`http://localhost:8000/api/v1/empresas/${empresaId}/sedes`);
            if (res.ok) {
                const data = await res.json();
                setSedesDisponibles(data);
                if (data.length > 0) {
                    setFormulario(f => ({ ...f, empresa_id: empresaId, sede_id: data[0].id }));
                } else {
                    setFormulario(f => ({ ...f, empresa_id: empresaId, sede_id: 'MANUAL' }));
                }
            }
        } catch (err) {
            console.error("Error al recuperar las sedes de la empresa:", err);
        }
    };

    useEffect(() => {
        obtenerEmpleados();
        obtenerSociedades();
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

    // 4. Desplegar el modal inyectando lo que capturó previamente la IA de manera dinámica
    const abrirModalEdicion = (emp) => {
        setEmpleadoSeleccionado(emp);

        const empresaIdActual = emp.empresa_id || sociedades[0]?.id || '';

        setFormulario({
            nombres: emp.nombres || '',
            apellidos: emp.apellidos || '',
            tipo_documento: emp.tipo_documento || '',
            numero_documento: emp.numero_documento || '',
            fecha_nacimiento: emp.fecha_nacimiento || '',
            lugar_expedicion: emp.lugar_expedicion || '',
            direccion_residencia: emp.direccion_residencia || '',
            telefono: emp.telefono || '',

            // 🛠️ Mapeo Multiempresa Dinámico Corregido 🛠️
            empresa_id: empresaIdActual,
            sede_id: emp.sede_id || '',
            aplica_sede: emp.sede_id !== -1,
            sede_manual: emp.sede_manual || '',

            tipo_contrato: emp.tipo_contrato || 'INDEFINIDO_ESTANDAR',
            cargo: emp.cargo || '',
            salario: emp.salario || '',
            fecha_ingreso: emp.fecha_ingreso || new Date().toISOString().split('T')[0]
        });

        // Carga dinámicamente las sedes de la empresa asociada al abrir el modal
        if (empresaIdActual) {
            cargarSedesDeEmpresa(empresaIdActual);
        }
    };

    // 5. Despachar aprobación final y disparar la creación de la plantilla de Google Docs
    const manejarAprobacionContrato = async (e) => {
        e.preventDefault();
        setCargandoContrato(true);

        let sedeIdFinal = formulario.sede_id;

        if (!formulario.aplica_sede) {
            sedeIdFinal = -1; // Le dice a Python: "No aplica"
        } else if (formulario.sede_id === "MANUAL") {
            sedeIdFinal = 0;  // Le dice a Python: "Usa el texto de 'sede_manual'"
        }

        try {
            const res = await fetch(`http://localhost:8000/api/v1/empleados/${empleadoSeleccionado.id}/aprobar`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    ...formulario,
                    empresa_id: parseInt(formulario.empresa_id), // Enviado explícitamente como entero
                    sede_id: parseInt(sedeIdFinal),              // Enviado explícitamente como entero
                    sede_manual: formulario.sede_id === "MANUAL" ? formulario.sede_manual : null
                })
            });
            const resultado = await res.json();

            if (res.ok && resultado.status === 'success') {
                alert("¡Candidato aprobado! Contrato inyectado y organizado en Google Drive.");
                if (resultado.contrato_url) {
                    window.open(resultado.contrato_url, '_blank'); // Abre el Google Doc de inmediato
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

            {/* SECCIÓN 2: CONSOLE DE GH */}
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

                {/* PAGINADOR */}
                <div style={{ marginTop: '20px', display: 'flex', gap: '10px', alignItems: 'center', justifyContent: 'center' }}>
                    <button disabled={paginaActual === 1} onClick={() => setPaginaActual(p => p - 1)} style={{ padding: '5px 10px', cursor: 'pointer' }}>Anterior</button>
                    <span style={{ fontSize: '14px', color: '#4a5568' }}>Página <strong>{paginaActual}</strong> de {totalPaginas || 1}</span>
                    <button disabled={paginaActual === totalPaginas || totalPaginas === 0} onClick={() => setPaginaActual(p => p + 1)} style={{ padding: '5px 10px', cursor: 'pointer' }}>Siguiente</button>
                </div>
            </section>

            {/* SECCIÓN 3: MODAL DE AUDITORÍA */}
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

                            <div style={{ display: 'flex', gap: '10px' }}>
                                <div style={{ flex: 1 }}>
                                    <label style={{ fontSize: '12px', fontWeight: 'bold', color: '#4a5568' }}>Lugar de Expedición:</label>
                                    <input type="text" value={formulario.lugar_expedicion} onChange={e => setFormulario({ ...formulario, lugar_expedicion: e.target.value })} style={{ width: '100%', padding: '8px', margin: '6px 0 12px 0', borderRadius: '4px', border: '1px solid #cbd5e0' }} />
                                </div>
                                <div style={{ flex: 1 }}>
                                    <label style={{ fontSize: '12px', fontWeight: 'bold', color: '#4a5568' }}>Fecha de Expedición:</label>
                                    <input type="date" value={formulario.fecha_expedicion} onChange={e => setFormulario({ ...formulario, fecha_expedicion: e.target.value })} style={{ width: '100%', padding: '8px', margin: '6px 0 12px 0', borderRadius: '4px', border: '1px solid #cbd5e0' }} />
                                </div>
                            </div>

                            <label style={{ fontSize: '12px', fontWeight: 'bold', color: '#4a5568' }}>Dirección de Residencia:</label>
                            <input type="text" value={formulario.direccion_residencia} onChange={e => setFormulario({ ...formulario, direccion_residencia: e.target.value })} placeholder="Ej: Avenida 15 # 103-24" style={{ width: '100%', padding: '8px', margin: '6px 0 12px 0', borderRadius: '4px', border: '1px solid #cbd5e0' }} />

                            <label style={{ fontSize: '12px', fontWeight: 'bold', color: '#4a5568' }}>Teléfono Celular:</label>
                            <input type="text" value={formulario.telefono} onChange={e => setFormulario({ ...formulario, telefono: e.target.value })} placeholder="Ej: 3124567890" style={{ width: '100%', padding: '8px', margin: '6px 0 12px 0', borderRadius: '4px', border: '1px solid #cbd5e0' }} />

                            <h4 style={{ color: '#4a5568', marginTop: '20px', marginBottom: '10px', borderBottom: '1px solid #edf2f7', paddingBottom: '5px' }}>2. Cláusulas y Datos de Contratación (Manual)</h4>

                            {/* 🏢 SELECTOR DE SOCIEDADES DINÁMICO */}
                            <label style={{ fontSize: '12px', fontWeight: 'bold', color: '#4a5568' }}>Sociedad / Empresa Contratante:</label>
                            <select
                                value={formulario.empresa_id}
                                onChange={e => {
                                    const id = e.target.value;
                                    setFormulario({ ...formulario, empresa_id: id });
                                    cargarSedesDeEmpresa(id); // Trae las sedes correctas al cambiar el combo
                                }}
                                style={{ width: '100%', padding: '8px', margin: '6px 0 12px 0', borderRadius: '4px', border: '1px solid #cbd5e0', backgroundColor: '#fff' }}
                            >
                                <option value="">-- Selecciona una Sociedad --</option>
                                {sociedades.map(soc => (
                                    <option key={soc.id} value={soc.id}>{soc.razon_social} (NIT: {soc.nit})</option>
                                ))}
                            </select>

                            {/* CHECKBOX DE SEDE FÍSICA */}
                            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', margin: '12px 0' }}>
                                <input
                                    type="checkbox"
                                    id="aplica_sede"
                                    checked={formulario.aplica_sede}
                                    onChange={e => setFormulario({ ...formulario, aplica_sede: e.target.checked })}
                                />
                                <label htmlFor="aplica_sede" style={{ fontSize: '13px', fontWeight: 'bold', color: '#4a5568', cursor: 'pointer' }}>
                                    ¿El cargo requiere ejecución en una Sede Física?
                                </label>
                            </div>

                            {/* SELECTOR DE SEDES ENCADENADO */}
                            {formulario.aplica_sede && (
                                <>
                                    <label style={{ fontSize: '12px', fontWeight: 'bold', color: '#4a5568' }}>Sede de Trabajo / Dirección:</label>
                                    <select
                                        value={formulario.sede_id}
                                        onChange={e => setFormulario({ ...formulario, sede_id: e.target.value })}
                                        style={{ width: '100%', padding: '8px', margin: '6px 0 12px 0', borderRadius: '4px', border: '1px solid #cbd5e0', backgroundColor: '#fff' }}
                                    >
                                        {sedesDisponibles.map(sede => (
                                            <option key={sede.id} value={sede.id}>{sede.nombre} — ({sede.direccion})</option>
                                        ))}
                                        <option value="MANUAL">✍️ OTRA (Digitar dirección manualmente)...</option>
                                    </select>

                                    {/* ENTRADA MANUAL COMPLEMENTARIA */}
                                    {formulario.sede_id === "MANUAL" && (
                                        <div style={{ backgroundColor: '#f7fafc', padding: '10px', borderRadius: '4px', border: '1px dashed #cbd5e0', marginBottom: '12px' }}>
                                            <label style={{ fontSize: '11px', fontWeight: 'bold', color: '#718096' }}>Nombre y ubicación de la Sede Nueva:</label>
                                            <input
                                                type="text"
                                                value={formulario.sede_manual}
                                                onChange={e => setFormulario({ ...formulario, sede_manual: e.target.value })}
                                                required
                                                placeholder="Ej: Oficina Satélite — Carrera 23 # 45-12, Manizales"
                                                style={{ width: '100%', padding: '8px', marginTop: '6px', borderRadius: '4px', border: '1px solid #cbd5e0', backgroundColor: '#fff' }}
                                            />
                                        </div>
                                    )}
                                </>
                            )}

                            <label style={{ fontSize: '12px', fontWeight: 'bold', color: '#4a5568' }}>Tipo de Contrato / Minuta:</label>
                            <select
                                value={formulario.tipo_contrato}
                                onChange={e => setFormulario({ ...formulario, tipo_contrato: e.target.value })}
                                style={{ width: '100%', padding: '8px', margin: '6px 0 12px 0', borderRadius: '4px', border: '1px solid #cbd5e0', backgroundColor: '#fff' }}
                            >
                                <option value="INDEFINIDO_ESTANDAR">Contrato Término Indefinido (Oficina)</option>
                                <option value="INDEFINIDO_ABITA">Contrato Término Indefinido (Turnos)</option>
                                <option value="FIJO">Contrato Término Fijo</option>
                                <option value="TIEMPO_PARCIAL">Contrato Tiempo Parcial</option>
                                <option value="PRESTACION_DESCUENTO">Prestación de Servicios (Con Descuento)</option>
                                <option value="PRESTACION_AUTONOMO">Prestación de Servicios (Autónomo)</option>
                            </select>

                            <label style={{ fontSize: '12px', fontWeight: 'bold', color: '#4a5568' }}>Cargo Estipulado:</label>
                            <input type="text" value={formulario.cargo} onChange={e => setFormulario({ ...formulario, cargo: e.target.value })} required placeholder="Ej: Ingeniero de Datos Senior" style={{ width: '100%', padding: '8px', margin: '6px 0 12px 0', borderRadius: '4px', border: '1px solid #cbd5e0' }} />

                            <label style={{ fontSize: '12px', fontWeight: 'bold', color: '#4a5568' }}>Salario Integral Mensual ($):</label>
                            <input type="text" value={formulario.salario} onChange={e => setFormulario({ ...formulario, salario: e.target.value })} required placeholder="Ej: 4800000" style={{ width: '100%', padding: '8px', margin: '6px 0 12px 0', borderRadius: '4px', border: '1px solid #cbd5e0' }} />

                            <label style={{ fontSize: '12px', fontWeight: 'bold', color: '#4a5568' }}>Fecha Oficial de Ingreso:</label>
                            <input type="date" value={formulario.fecha_ingreso} onChange={e => setFormulario({ ...formulario, fecha_ingreso: e.target.value })} required style={{ width: '100%', padding: '8px', margin: '6px 0 20px 0', borderRadius: '4px', border: '1px solid #cbd5e0' }} />

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