                const Json fields=request.value("fields",Json::object());
                for (const auto& item:fields.items())
                    message.set(item.key(),item.value().get<std::string>());
