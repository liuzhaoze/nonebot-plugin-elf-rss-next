from arclet.alconna import Alconna, Args, MultiVar, Subcommand

alconna = Alconna(
    "elf",
    Subcommand("help"),
    Subcommand("add", Args["name", str]["url", str]),
    Subcommand("del", Args["names", MultiVar(str)]),
    Subcommand("ls"),
    Subcommand("info", Args["name", str]),
    Subcommand("edit", Args["name", str]["options", MultiVar(str)]),
)
