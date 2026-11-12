//! Loading and saving `world.bin`, on native (file dialogs, filesystem) and
//! on the web (`<input type=file>` upload, download). Results arrive as
//! [`FileEvent`]s polled once per frame, so both platforms share one path.

use std::sync::mpsc::{channel, Receiver, Sender};

pub enum FileEvent {
    Loaded { name: String, bytes: Vec<u8> },
    Saved(String),
    Error(String),
}

pub struct Files {
    tx: Sender<FileEvent>,
    rx: Receiver<FileEvent>,
}

const FILTER_NAME: &str = "Neolith world";
const FILTER_EXT: &[&str] = &["bin"];

impl Default for Files {
    fn default() -> Self {
        let (tx, rx) = channel();
        Self { tx, rx }
    }
}

impl Files {
    pub fn poll(&self) -> Option<FileEvent> {
        self.rx.try_recv().ok()
    }
}

#[cfg(not(target_arch = "wasm32"))]
impl Files {
    /// Loads the startup world: the given path, or `assets/world.bin` found
    /// relative to the working directory, the executable or the source tree.
    pub fn load_default(&self, _ctx: &egui::Context, path: Option<String>) {
        use std::path::PathBuf;
        let candidates: Vec<PathBuf> = match path {
            Some(p) => vec![p.into()],
            None => {
                let mut c = vec![PathBuf::from("assets/world.bin"), PathBuf::from("neolith-rs/assets/world.bin")];
                if let Some(dir) = std::env::current_exe().ok().and_then(|e| e.parent().map(|d| d.to_path_buf())) {
                    c.push(dir.join("world.bin"));
                    c.push(dir.join("assets/world.bin"));
                    c.push(dir.join("../../assets/world.bin"));
                }
                c.push(PathBuf::from(concat!(env!("CARGO_MANIFEST_DIR"), "/../../assets/world.bin")));
                c
            }
        };
        for path in &candidates {
            if let Ok(bytes) = std::fs::read(path) {
                let _ = self.tx.send(FileEvent::Loaded { name: path.display().to_string(), bytes });
                return;
            }
        }
        let tried = candidates.iter().map(|p| p.display().to_string()).collect::<Vec<_>>().join(", ");
        let _ = self.tx.send(FileEvent::Error(format!(
            "could not find a world file (tried: {tried}). Generate one with `neolith-convert`, or pass a path."
        )));
    }

    pub fn open_dialog(&self, _ctx: &egui::Context) {
        if let Some(path) = rfd::FileDialog::new().add_filter(FILTER_NAME, FILTER_EXT).pick_file() {
            let ev = match std::fs::read(&path) {
                Ok(bytes) => FileEvent::Loaded { name: path.display().to_string(), bytes },
                Err(e) => FileEvent::Error(format!("cannot read {}: {e}", path.display())),
            };
            let _ = self.tx.send(ev);
        }
    }

    pub fn save_dialog(&self, _ctx: &egui::Context, bytes: Vec<u8>) {
        let dialog = rfd::FileDialog::new().add_filter(FILTER_NAME, FILTER_EXT).set_file_name("world.bin");
        if let Some(path) = dialog.save_file() {
            let ev = match std::fs::write(&path, bytes) {
                Ok(()) => FileEvent::Saved(path.display().to_string()),
                Err(e) => FileEvent::Error(format!("cannot write {}: {e}", path.display())),
            };
            let _ = self.tx.send(ev);
        }
    }
}

#[cfg(target_arch = "wasm32")]
impl Files {
    /// Fetches `world.bin` from next to the page.
    pub fn load_default(&self, ctx: &egui::Context, path: Option<String>) {
        let url = path.unwrap_or_else(|| "world.bin".to_string());
        let (tx, ctx) = (self.tx.clone(), ctx.clone());
        ehttp::fetch(ehttp::Request::get(&url), move |result| {
            let ev = match result {
                Ok(resp) if resp.ok => FileEvent::Loaded { name: url.clone(), bytes: resp.bytes },
                Ok(resp) => FileEvent::Error(format!("cannot fetch {url}: HTTP {} {}", resp.status, resp.status_text)),
                Err(e) => FileEvent::Error(format!("cannot fetch {url}: {e}")),
            };
            let _ = tx.send(ev);
            ctx.request_repaint();
        });
    }

    pub fn open_dialog(&self, ctx: &egui::Context) {
        let (tx, ctx) = (self.tx.clone(), ctx.clone());
        wasm_bindgen_futures::spawn_local(async move {
            if let Some(file) = rfd::AsyncFileDialog::new().add_filter(FILTER_NAME, FILTER_EXT).pick_file().await {
                let bytes = file.read().await;
                let _ = tx.send(FileEvent::Loaded { name: file.file_name(), bytes });
                ctx.request_repaint();
            }
        });
    }

    /// On the web "saving" downloads the file.
    pub fn save_dialog(&self, ctx: &egui::Context, bytes: Vec<u8>) {
        let (tx, ctx) = (self.tx.clone(), ctx.clone());
        wasm_bindgen_futures::spawn_local(async move {
            if let Some(file) = rfd::AsyncFileDialog::new().set_file_name("world.bin").save_file().await {
                let ev = match file.write(&bytes).await {
                    Ok(()) => FileEvent::Saved(file.file_name()),
                    Err(e) => FileEvent::Error(format!("download failed: {e}")),
                };
                let _ = tx.send(ev);
                ctx.request_repaint();
            }
        });
    }
}
