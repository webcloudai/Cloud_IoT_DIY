/*
© 2022 Daniil Sokolov (daniil.sokolov@webcloudai.com)
MIT License 
*/
import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import 'package:provider/provider.dart';
import 'authentication_provider.dart';

class CustomAppBar extends StatelessWidget implements PreferredSizeWidget {
  final String titleText;
  @override
  Size get preferredSize => const Size.fromHeight(kToolbarHeight);

  const CustomAppBar({Key? key, this.titleText = 'Main Page'})
      : super(key: key);

  @override
  Widget build(BuildContext context) {
    var role = context.watch<AuthenticationProvider>().role;

    return AppBar(
      title: Text(titleText),
      // backgroundColor: primaryColor,
      actions: [
        // Common action for all users
        IconButton(
          icon: const Icon(Icons.home),
          onPressed: () {
            // Navigator.pushNamed(context, '/');
            context.pushNamed("home");
          },
        ),
        // Action visible only for authenticated users
        if (role != null)
          IconButton(
            icon: const Icon(Icons.dashboard),
            onPressed: () {
              // Navigator.pushNamed(context, '/dashboard');
              context.pushNamed("dashboard");
            },
          ),
        // Action visible only for admin users
        // if (role == 'admin')
        if (role != null)
          IconButton(
            icon: const Icon(Icons.touch_app),
            onPressed: () {
              // Navigator.pushNamed(context, '/admin');
              context.pushNamed("account");
            },
          ),
      ],
    );
  }
}
