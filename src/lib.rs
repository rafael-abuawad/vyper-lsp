use std::collections::HashMap;

use zed_extension_api::{self as zed, serde_json::Value, settings::LspSettings};

const COMPILER_SERVER: &str = include_str!("compiler_server.py");
const VENV_DIRECTORY: &str = "vyper-lsp-venv";

struct VyperExtension {
    using_fallback: bool,
}

impl zed::Extension for VyperExtension {
    fn new() -> Self {
        Self {
            using_fallback: false,
        }
    }

    fn language_server_command(
        &mut self,
        language_server_id: &zed::LanguageServerId,
        worktree: &zed::Worktree,
    ) -> zed::Result<zed::Command> {
        let settings = lsp_settings(language_server_id, worktree);
        if let Some(command) = configured_server(&settings) {
            self.using_fallback = false;
            eprintln!(
                "vyper: launching configured language server {}",
                command.command
            );
            return Ok(command);
        }
        if let Some(command) = worktree.which("vyper-lsp") {
            self.using_fallback = false;
            eprintln!("vyper: launching {command}");
            return Ok(zed::Command {
                command,
                args: Vec::new(),
                env: Vec::new(),
            });
        }
        if let Some(command) = installed_vyper_lsp() {
            self.using_fallback = false;
            eprintln!("vyper: launching installed {command}");
            return Ok(zed::Command {
                command,
                args: Vec::new(),
                env: Vec::new(),
            });
        }

        match install_vyper_lsp(language_server_id, worktree) {
            Ok(command) => {
                self.using_fallback = false;
                eprintln!("vyper: launching installed {command}");
                return Ok(zed::Command {
                    command,
                    args: Vec::new(),
                    env: Vec::new(),
                });
            }
            Err(install_error) => {
                eprintln!("vyper: install failed: {install_error}");
                zed::set_language_server_installation_status(
                    language_server_id,
                    &zed::LanguageServerInstallationStatus::None,
                );
                self.using_fallback = true;
                match compiler_server_command(worktree, &vyper_command(&settings)) {
                    Ok(command) => Ok(command),
                    Err(fallback_error) => {
                        let message = format!(
                            "Could not install vyper-lsp: {install_error} {fallback_error}"
                        );
                        zed::set_language_server_installation_status(
                            language_server_id,
                            &zed::LanguageServerInstallationStatus::Failed(message.clone()),
                        );
                        Err(message)
                    }
                }
            }
        }
    }

    fn language_server_initialization_options(
        &mut self,
        language_server_id: &zed::LanguageServerId,
        worktree: &zed::Worktree,
    ) -> zed::Result<Option<Value>> {
        let settings = lsp_settings(language_server_id, worktree);
        let mut options = settings
            .initialization_options
            .clone()
            .unwrap_or_else(|| Value::Object(Default::default()));

        if self.using_fallback {
            if let Some(object) = options.as_object_mut() {
                object
                    .entry("command")
                    .or_insert_with(|| Value::String(vyper_command(&settings)));
            }
        }

        if options.as_object().is_some_and(|object| object.is_empty()) {
            return Ok(None);
        }
        Ok(Some(options))
    }

    fn language_server_workspace_configuration(
        &mut self,
        language_server_id: &zed::LanguageServerId,
        worktree: &zed::Worktree,
    ) -> zed::Result<Option<Value>> {
        Ok(lsp_settings(language_server_id, worktree).settings)
    }
}

fn lsp_settings(
    language_server_id: &zed::LanguageServerId,
    worktree: &zed::Worktree,
) -> LspSettings {
    LspSettings::for_worktree(language_server_id.as_ref(), worktree).unwrap_or_default()
}

fn configured_server(settings: &LspSettings) -> Option<zed::Command> {
    let binary = settings.binary.as_ref()?;
    let command = binary.path.clone()?;
    Some(zed::Command {
        command,
        args: binary.arguments.clone().unwrap_or_default(),
        env: env_pairs(binary.env.clone()),
    })
}

fn vyper_command(settings: &LspSettings) -> String {
    settings
        .settings
        .as_ref()
        .and_then(|settings| settings.get("command"))
        .and_then(Value::as_str)
        .map(str::trim)
        .filter(|command| !command.is_empty())
        .unwrap_or("vyper")
        .to_string()
}

fn installed_vyper_lsp() -> Option<String> {
    let directory = extension_directory().ok()?;
    let binary = venv_executable(&format!("{directory}/{VENV_DIRECTORY}"), "vyper-lsp");
    is_file(&binary).then_some(binary)
}

fn install_vyper_lsp(
    language_server_id: &zed::LanguageServerId,
    worktree: &zed::Worktree,
) -> zed::Result<String> {
    let directory = extension_directory()?;
    let venv = format!("{directory}/{VENV_DIRECTORY}");
    let binary = venv_executable(&venv, "vyper-lsp");
    if is_file(&binary) {
        return Ok(binary);
    }

    zed::set_language_server_installation_status(
        language_server_id,
        &zed::LanguageServerInstallationStatus::CheckingForUpdate,
    );
    let _ = std::fs::remove_dir_all(&venv);
    zed::set_language_server_installation_status(
        language_server_id,
        &zed::LanguageServerInstallationStatus::Downloading,
    );

    let mut errors = Vec::new();
    if let Some(uv) = worktree.which("uv") {
        eprintln!("vyper: installing vyper-lsp with uv into {venv}");
        match install_with_uv(&uv, &venv) {
            Ok(()) if is_file(&binary) => {
                zed::set_language_server_installation_status(
                    language_server_id,
                    &zed::LanguageServerInstallationStatus::None,
                );
                return Ok(binary);
            }
            Ok(()) => errors.push("uv finished without producing a vyper-lsp binary".to_string()),
            Err(error) => errors.push(error),
        }
        let _ = std::fs::remove_dir_all(&venv);
    }

    if let Some(python) = python_for_venv(worktree) {
        eprintln!("vyper: installing vyper-lsp with {python} into {venv}");
        match install_with_python(&python, &venv) {
            Ok(()) if is_file(&binary) => {
                zed::set_language_server_installation_status(
                    language_server_id,
                    &zed::LanguageServerInstallationStatus::None,
                );
                return Ok(binary);
            }
            Ok(()) => {
                errors.push("python finished without producing a vyper-lsp binary".to_string())
            }
            Err(error) => errors.push(error),
        }
    } else if errors.is_empty() {
        errors.push(
            "uv is not installed, and Python 3.12 or newer was not found. vyper-lsp requires Python 3.12."
                .to_string(),
        );
    }

    Err(errors.join(" "))
}

fn install_with_uv(uv: &str, venv: &str) -> zed::Result<()> {
    run(uv, &["venv", "--python", "3.12", venv])?;
    let python = venv_executable(venv, "python");
    run(uv, &["pip", "install", "--python", &python, "vyper-lsp"])
}

fn install_with_python(python: &str, venv: &str) -> zed::Result<()> {
    run(python, &["-m", "venv", venv])?;
    let pip = venv_executable(venv, "pip");
    run(&pip, &["install", "vyper-lsp"])
}

fn python_for_venv(worktree: &zed::Worktree) -> Option<String> {
    let python = worktree
        .which("python3")
        .or_else(|| worktree.which("python"))?;
    let mut command = zed::process::Command::new(&python)
        .arg("-c")
        .arg("import sys; raise SystemExit(0 if sys.version_info >= (3, 12) else 1)");
    command
        .output()
        .ok()
        .filter(|output| output.status == Some(0))
        .map(|_| python)
}

fn venv_executable(venv: &str, name: &str) -> String {
    let (os, _) = zed::current_platform();
    match os {
        zed::Os::Windows => format!("{venv}/Scripts/{name}.exe"),
        zed::Os::Mac | zed::Os::Linux => format!("{venv}/bin/{name}"),
    }
}

fn is_file(path: &str) -> bool {
    std::fs::metadata(path).is_ok_and(|metadata| metadata.is_file())
}

fn run(program: &str, args: &[&str]) -> zed::Result<()> {
    eprintln!("vyper: {program} {}", args.join(" "));
    let mut command = zed::process::Command::new(program).args(args.iter().copied());
    let output = command
        .output()
        .map_err(|error| format!("failed to run {program}: {error}"))?;
    if output.status == Some(0) {
        return Ok(());
    }

    let mut detail = String::from_utf8_lossy(&output.stderr).into_owned();
    detail.push_str(&String::from_utf8_lossy(&output.stdout));
    let detail = detail.trim();
    let tail = if detail.len() > 1500 {
        &detail[detail.len() - 1500..]
    } else {
        detail
    };
    Err(format!(
        "{program} exited with status {:?}: {tail}",
        output.status
    ))
}

fn compiler_server_command(
    worktree: &zed::Worktree,
    vyper_command: &str,
) -> zed::Result<zed::Command> {
    let python = worktree.which("python3").or_else(|| worktree.which("python")).ok_or_else(|| {
        "vyper-lsp was not found, and neither was python3. Install vyper-lsp with `pipx install git+https://github.com/vyperlang/vyper-lsp.git`, or install Python 3 and the vyper compiler.".to_string()
    })?;

    let directory = extension_directory()?;
    let script = format!("{directory}/vyper_compiler_server.py");
    std::fs::write(&script, COMPILER_SERVER)
        .map_err(|error| format!("failed to write the Vyper compiler server: {error}"))?;

    eprintln!("vyper: vyper-lsp is not on PATH, using the built-in compiler server ({python})");
    Ok(zed::Command {
        command: python,
        args: vec![script],
        env: vec![("VYPER_COMMAND".into(), vyper_command.into())],
    })
}

fn extension_directory() -> zed::Result<String> {
    if let Ok(pwd) = std::env::var("PWD") {
        let pwd = pwd.trim_end_matches(['/', '\\']);
        if !pwd.is_empty() {
            return Ok(pwd.to_string());
        }
    }
    std::env::current_dir()
        .map(|path| {
            path.to_string_lossy()
                .trim_end_matches(['/', '\\'])
                .to_string()
        })
        .map_err(|error| format!("could not locate the extension directory: {error}"))
}

fn env_pairs(env: Option<HashMap<String, String>>) -> Vec<(String, String)> {
    env.unwrap_or_default().into_iter().collect()
}

zed::register_extension!(VyperExtension);
