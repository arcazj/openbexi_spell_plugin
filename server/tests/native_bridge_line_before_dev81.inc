        while (std::cin.good()) {
            std::string line;
            char ch;
            while (std::cin.get(ch) && ch!='\n') {
                if (line.size()>=4*1024*1024) throw std::runtime_error("Host message exceeds 4 MiB");
                line+=ch;
            }
            if (line.empty()) break;
