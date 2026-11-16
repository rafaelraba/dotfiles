return {
  {
    "stevearc/oil.nvim",
    keys = {
      { "-", "<cmd>Oil<cr>", desc = "Open parent directory" },
    },
    opts = {
      default_file_explorer = false,
      restore_win_options = true,
      view_options = {
        show_hidden = true,
        is_always_hidden = function(name)
          return name == ".." or name == ".git"
        end,
        natural_order = true,
      },
    },
    dependencies = { "nvim-tree/nvim-web-devicons" },
  },
}
