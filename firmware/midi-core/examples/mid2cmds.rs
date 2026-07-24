// Хост-утилита: .mid -> бинарный поток команд chipbox (для chipbox_tb --cmds)
fn main() {
    let args: Vec<String> = std::env::args().collect();
    if args.len() != 3 {
        eprintln!("usage: mid2cmds <in.mid> <out.bin>");
        std::process::exit(1);
    }
    let data = std::fs::read(&args[1]).unwrap();
    let cmds = midi_core::midi_to_commands(&data).unwrap();
    let mut out: Vec<u8> = Vec::with_capacity(cmds.len() * 4);
    for c in &cmds {
        out.extend(c.to_le_bytes());
    }
    std::fs::write(&args[2], out).unwrap();
    eprintln!("{} команд -> {}", cmds.len(), args[2]);
}
