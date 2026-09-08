use serde::Serialize;
use std::{
    io::{BufRead, BufReader, Write},
    net::{SocketAddr, TcpListener, TcpStream},
    path::PathBuf,
    process::{Child, Command, Stdio},
    sync::Mutex,
    thread,
    time::{Duration, Instant},
};
use tauri::{path::BaseDirectory, AppHandle, Manager, RunEvent, State};
use uuid::Uuid;

const SIDECAR_RESOURCE_PATH: &str = "sidecar/swing-scanner-sidecar";
const SHUTDOWN_TIMEOUT: Duration = Duration::from_secs(3);

#[derive(Clone, Serialize)]
#[serde(rename_all = "camelCase")]
struct DesktopRuntimeConfig {
    base_url: String,
    bearer_token: String,
    mode: &'static str,
}

struct BackendRuntime {
    child: Child,
    config: DesktopRuntimeConfig,
    port: u16,
}

#[derive(Default)]
struct BackendStateInner {
    runtime: Option<BackendRuntime>,
    startup_error: Option<String>,
}

#[derive(Default)]
struct DesktopBackendState {
    inner: Mutex<BackendStateInner>,
}

#[tauri::command]
fn desktop_runtime_config(
    state: State<'_, DesktopBackendState>,
) -> Result<DesktopRuntimeConfig, String> {
    let mut inner = state
        .inner
        .lock()
        .map_err(|_| "Desktop backend state is unavailable".to_string())?;

    if let Some(runtime) = inner.runtime.as_mut() {
        match runtime.child.try_wait() {
            Ok(Some(status)) => {
                let message = format!("Desktop backend exited before startup ({status})");
                inner.runtime = None;
                inner.startup_error = Some(message.clone());
                return Err(message);
            }
            Ok(None) => return Ok(runtime.config.clone()),
            Err(error) => return Err(format!("Unable to inspect desktop backend: {error}")),
        }
    }

    Err(inner
        .startup_error
        .clone()
        .unwrap_or_else(|| "Desktop backend has not started".to_string()))
}

#[tauri::command]
fn restart_desktop_backend(
    app: AppHandle,
    state: State<'_, DesktopBackendState>,
) -> Result<DesktopRuntimeConfig, String> {
    stop_backend(&state);
    let result = start_backend(&app);
    let mut inner = state
        .inner
        .lock()
        .map_err(|_| "Desktop backend state is unavailable".to_string())?;

    match result {
        Ok(runtime) => {
            let config = runtime.config.clone();
            inner.runtime = Some(runtime);
            inner.startup_error = None;
            Ok(config)
        }
        Err(error) => {
            inner.startup_error = Some(error.clone());
            Err(error)
        }
    }
}

fn start_backend(app: &AppHandle) -> Result<BackendRuntime, String> {
    let port = available_loopback_port()?;
    let token = format!("{}{}", Uuid::new_v4().simple(), Uuid::new_v4().simple());
    let executable = resolve_sidecar_path(app)?;
    let cache_dir = app
        .path()
        .app_cache_dir()
        .map_err(|error| format!("Unable to resolve desktop cache directory: {error}"))?
        .join("phase-zero");
    let matplotlib_dir = cache_dir.join("matplotlib");
    std::fs::create_dir_all(&matplotlib_dir)
        .map_err(|error| format!("Unable to create desktop cache directory: {error}"))?;

    let mut child = Command::new(&executable)
        .current_dir(&cache_dir)
        .env("SCANNER_DESKTOP_PORT", port.to_string())
        .env("SCANNER_DESKTOP_TOKEN", &token)
        .env("MPLCONFIGDIR", matplotlib_dir)
        .stdin(Stdio::null())
        .stdout(Stdio::piped())
        .stderr(Stdio::piped())
        .spawn()
        .map_err(|error| {
            format!(
                "Unable to start the packaged desktop backend at {}: {error}",
                executable.display()
            )
        })?;

    if let Some(stdout) = child.stdout.take() {
        forward_sidecar_output("backend", stdout);
    }
    if let Some(stderr) = child.stderr.take() {
        forward_sidecar_output("backend error", stderr);
    }

    Ok(BackendRuntime {
        child,
        config: DesktopRuntimeConfig {
            base_url: format!("http://127.0.0.1:{port}"),
            bearer_token: token,
            mode: "desktop-proof-of-concept",
        },
        port,
    })
}

fn resolve_sidecar_path(app: &AppHandle) -> Result<PathBuf, String> {
    let bundled_path = app
        .path()
        .resolve(SIDECAR_RESOURCE_PATH, BaseDirectory::Resource)
        .map_err(|error| format!("Unable to resolve packaged backend: {error}"))?;
    if bundled_path.is_file() {
        return Ok(bundled_path);
    }

    if cfg!(debug_assertions) {
        let development_path = PathBuf::from(env!("CARGO_MANIFEST_DIR"))
            .join("resources")
            .join("swing-scanner-sidecar")
            .join("swing-scanner-sidecar");
        if development_path.is_file() {
            return Ok(development_path);
        }
    }

    Err(format!(
        "Packaged desktop backend was not found at {}",
        bundled_path.display()
    ))
}

fn available_loopback_port() -> Result<u16, String> {
    let listener = TcpListener::bind(("127.0.0.1", 0))
        .map_err(|error| format!("Unable to reserve a desktop backend port: {error}"))?;
    let port = listener
        .local_addr()
        .map_err(|error| format!("Unable to read the desktop backend port: {error}"))?
        .port();
    drop(listener);
    Ok(port)
}

fn forward_sidecar_output<R>(label: &'static str, reader: R)
where
    R: std::io::Read + Send + 'static,
{
    thread::spawn(move || {
        for line in BufReader::new(reader).lines().map_while(Result::ok) {
            eprintln!("[{label}] {line}");
        }
    });
}

fn stop_backend(state: &DesktopBackendState) {
    let runtime = state
        .inner
        .lock()
        .ok()
        .and_then(|mut inner| inner.runtime.take());
    let Some(mut runtime) = runtime else {
        return;
    };

    if matches!(runtime.child.try_wait(), Ok(Some(_))) {
        return;
    }

    request_graceful_shutdown(&runtime);
    let deadline = Instant::now() + SHUTDOWN_TIMEOUT;
    while Instant::now() < deadline {
        match runtime.child.try_wait() {
            Ok(Some(_)) => return,
            Ok(None) => thread::sleep(Duration::from_millis(50)),
            Err(_) => break,
        }
    }

    let _ = runtime.child.kill();
    let _ = runtime.child.wait();
}

fn request_graceful_shutdown(runtime: &BackendRuntime) {
    let address = SocketAddr::from(([127, 0, 0, 1], runtime.port));
    let Ok(mut stream) = TcpStream::connect_timeout(&address, Duration::from_millis(500)) else {
        return;
    };
    let _ = stream.set_write_timeout(Some(Duration::from_millis(500)));
    let request = format!(
        "POST /api/desktop/shutdown HTTP/1.1\r\nHost: 127.0.0.1:{}\r\nAuthorization: Bearer {}\r\nContent-Length: 0\r\nConnection: close\r\n\r\n",
        runtime.port, runtime.config.bearer_token
    );
    let _ = stream.write_all(request.as_bytes());
    let _ = stream.flush();
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    let application = tauri::Builder::default()
        .manage(DesktopBackendState::default())
        .invoke_handler(tauri::generate_handler![
            desktop_runtime_config,
            restart_desktop_backend
        ])
        .setup(|app| {
            let state = app.state::<DesktopBackendState>();
            let mut inner = state
                .inner
                .lock()
                .map_err(|_| "Desktop backend state is unavailable")?;
            match start_backend(app.handle()) {
                Ok(runtime) => inner.runtime = Some(runtime),
                Err(error) => inner.startup_error = Some(error),
            }
            Ok(())
        })
        .build(tauri::generate_context!())
        .expect("error while building Swing Scanner desktop application");

    application.run(|app, event| {
        if matches!(event, RunEvent::ExitRequested { .. } | RunEvent::Exit) {
            stop_backend(&app.state::<DesktopBackendState>());
        }
    });
}
