use zed_extension_api as zed;

struct VyperExtension;

impl zed::Extension for VyperExtension {
    fn new() -> Self {
        Self
    }

    fn language_server_command(
        &mut self,
        _language_server_id: &zed::LanguageServerId,
        worktree: &zed::Worktree,
    ) -> zed::Result<zed::Command> {
        let command = worktree.which("vyper-lsp").ok_or_else(|| {
            "vyper-lsp was not found on PATH. Install it with `pipx install git+https://github.com/vyperlang/vyper-lsp.git`."
                .to_string()
        })?;

        Ok(zed::Command {
            command,
            args: Vec::new(),
            env: Vec::new(),
        })
    }
}

zed::register_extension!(VyperExtension);
