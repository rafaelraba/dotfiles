return {
  -- JetBrains' official Neovim client for the IntelliJ language server.
  -- Scope: Java and Kotlin only (filetypes are fixed in the plugin's defaults).
  -- Do NOT lazy-load on ft: the Maven/Gradle import starts from the build file
  -- inside the project directory, before any source file is opened.
  --
  -- NOTE: nvim-dap is deliberately a plain dependency without `opts`. lazy.nvim
  -- propagates a spec's `opts` to its dependencies, and nvim-dap has no setup()
  -- function, so `opts = {}` here breaks it with "dap.setup is nil".
  -- NOTE: do not also enable lazyvim.plugins.extras.lang.java; nvim-jdtls and
  -- intellij-lsp would both attach to the same Java/Kotlin buffers.
  -- nvim-dap gets an explicit no-op config on purpose.
  --
  -- LazyVim's typescript extra (enabled in lazyvim.json) declares an `optional`
  -- nvim-dap spec that only adds `opts`, assuming lazyvim.plugins.extras.dap.core
  -- is enabled. That extra is off here, so nothing defines a `config` for
  -- nvim-dap. lazy.nvim sees `opts` with no config and runs require("dap").setup(),
  -- which does not exist -> "attempt to call field 'setup' (a nil value)".
  --
  -- lazy.nvim evaluates the opts function before calling config, so the js-debug
  -- adapters from the typescript extra are still registered; only the bogus
  -- setup() call is skipped.
  {
    "mfussenegger/nvim-dap",
    config = function() end,
  },
  {
    "JetBrains/intellij-lsp.nvim",
    dependencies = { "mfussenegger/nvim-dap" },
    config = function()
      require("intellij-lsp").setup({
        -- The server bundle needs an IntelliJ IDEA Ultimate licence after the
        -- 30-day trial. Sign in with :IntellijLspLicense.
        -- EULA, region and usage statistics are answered on first start.
        format_on_save = false,
        decompiler = true,
        -- Fallback JDK for projects with no Maven/Gradle/Bazel/JPS build file.
        -- java/17: dossier targets sourceCompatibility 17. Points at the mise
        -- symlink, so patch upgrades keep working.
        default_sdk = vim.fn.expand("~/.local/share/mise/installs/java/17"),
      })
    end,
  },
}
