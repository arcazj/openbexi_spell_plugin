                SPELLipcMessage message(request.at("id").get<std::string>());
                message.setSender("GUI");message.setReceiver(request.at("receiver").get<std::string>());
                // The request owns these fields throughout this synchronous loop.
                // set() transfers independently owned strings into the native message.
                const auto fields=request.find("fields");
                if (fields!=request.end())
                    for (const auto& item:fields->items())
                        message.set(item.key(),item.value().get<std::string>());
