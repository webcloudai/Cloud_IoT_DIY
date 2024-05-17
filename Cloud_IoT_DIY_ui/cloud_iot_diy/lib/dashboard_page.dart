/*
© 2022 Daniil Sokolov (daniil.sokolov@webcloudai.com)
MIT License 
*/
import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'dashboard_provider.dart';
import 'authentication_provider.dart';
import 'dart:math';

class DashboardPage extends StatefulWidget {
  const DashboardPage({
    Key? key,
  }) : super(key: key);

  @override
  DashboardPageState createState() => DashboardPageState();
}

class DashboardPageState extends State<DashboardPage>
    with AutomaticKeepAliveClientMixin {
  List<String> availableDataSources = [];
  final TextEditingController _textFieldController = TextEditingController();
  // dashboard can be loaded from the backend
  String? loadedDashboard;
  // dashboard diagrams params
  int maxNumberInRow = 3;
  int maxTileSize = 600;
  int minTileSize = 300;

  @override
  bool get wantKeepAlive => true;

  void _saveDashboard() {
    showDialog(
      context: context,
      builder: (context) {
        return AlertDialog(
          title: const Text('Enter the name for the dashboard'),
          content: TextField(
            controller: _textFieldController,
            decoration: const InputDecoration(hintText: "Dashboard name"),
          ),
          actions: <Widget>[
            TextButton(
              child: const Text('CANCEL'),
              onPressed: () {
                Navigator.of(context).pop();
              },
            ),
            TextButton(
              child: const Text('SAVE'),
              onPressed: () async {
                var dashboardName = _textFieldController.text;
                // Collect access token for access token
                var authProvider =
                    Provider.of<AuthenticationProvider>(context, listen: false);
                // Collect dashboard details
                await context.read<DashboardProvider>().saveDashboardAs(
                    dashboardName, await authProvider.getAccessToken());

                if (context.mounted) Navigator.of(context).pop();
                // Navigator.of(context).pop();
              },
            ),
          ],
        );
      },
    );
  }

  Future<List<String>?> availableDashboards() async {
    List<String> dashboards =
        await Provider.of<AuthenticationProvider>(context, listen: false)
            .getAvailableDashboards(true);
    return dashboards;
  }

  /// Load dashboard from the API
  Future<void> collectDashboard(String dashboardName) async {
    var authProv = Provider.of<AuthenticationProvider>(context, listen: false);
    await Provider.of<DashboardProvider>(context, listen: false)
        .loadDashboardWithId(dashboardName, await authProv.getAccessToken());
  }

  /// Show dialog to load the dashboard from the backend
  void _loadDashboard() async {
    String? selectedDashboard;
    await showDialog(
        context: context,
        builder: (context) {
          return FutureBuilder<List<String>?>(
            future: availableDashboards(),
            builder: (context, snapshot) {
              if (snapshot.hasError) {
                return Text('Error: ${snapshot.error}');
              } else if (snapshot.data != null) {
                return StatefulBuilder(
                  builder: (context, setState) {
                    return AlertDialog(
                      title: const Text('Select a dashboard to load'),
                      content: DropdownButton<String>(
                        hint: const Text("Select dashboard"),
                        value: selectedDashboard,
                        isExpanded: true,
                        items: snapshot.data!
                            .map<DropdownMenuItem<String>>((String value) {
                          return DropdownMenuItem<String>(
                            value: value,
                            child: Text(value),
                          );
                        }).toList(),
                        onChanged: (String? newValue) {
                          setState(() {
                            selectedDashboard = newValue!;
                          });
                        },
                      ),
                      actions: <Widget>[
                        TextButton(
                          child: const Text('CANCEL'),
                          onPressed: () {
                            if (context.mounted) Navigator.of(context).pop();
                          },
                        ),
                        TextButton(
                          onPressed: selectedDashboard == null
                              ? null
                              : () async {
                                  // Here you should load the selected dashboard.
                                  // This could involve making another API call with the selected dashboard name and then updating the DashboardNotifier with the returned data.
                                  await collectDashboard(selectedDashboard!);
                                  // .then((value) => //{
                                  if (context.mounted) {
                                    // Navigator.of(context).pop();
                                    Navigator.pop(context, selectedDashboard);
                                  }
                                  //}
                                  // );
                                },
                          child: const Text('LOAD'),
                        ),
                      ],
                    );
                  },
                );
              }
              return const CircularProgressIndicator();
            },
          );
          // return const CircularProgressIndicator();
        });
    if (selectedDashboard != null) {
      setState(() {
        loadedDashboard = selectedDashboard;
      });
    }
  }

  @override
  Widget build(BuildContext context) =>
      Consumer<AuthenticationProvider>(builder: (context, authProvider, child) {
        super.build(context);
        // return FutureBuilder<List<String>>(
        return FutureBuilder<Map<String, List<String>>>(
            // future: authProvider.getAvailableDevices(false),
            future: authProvider.getPreliminaryData(false),
            builder:
                // (BuildContext context, AsyncSnapshot<List<String>> snapshot) {
                (BuildContext context,
                    AsyncSnapshot<Map<String, List<String>>> snapshot) {
              if (snapshot.connectionState == ConnectionState.waiting) {
                return const Row(
                    mainAxisAlignment: MainAxisAlignment.spaceAround,
                    children: [
                      SizedBox(
                          width: 100,
                          height: 100,
                          child: CircularProgressIndicator())
                    ]);
              } else if (snapshot.hasError) {
                return Text('Error: ${snapshot.error}');
              } else {
                // add list of available devices (datasources) to DashboardProvider
                Provider.of<DashboardProvider>(context, listen: false)
                    .availableDataSources = snapshot.data!["devices"] ?? [];
                // we need to load the dashboard if first load and "current" returned
                //
                return Scaffold(
                  appBar: AppBar(
                    title: const Text('Dashboard'),
                    actions: <Widget>[
                      IconButton(
                        icon: const Icon(Icons.addchart),
                        onPressed: () {
                          if (snapshot.hasData) {
                            final dataSources = snapshot.data!["devices"];
                            context
                                .read<DashboardProvider>()
                                .addTile(dataSources!);
                            // .addItem(dataSources!);
                          }
                        },
                      ),
                      // IconButton(
                      //   icon: const Icon(Icons.add),
                      //   onPressed: () {
                      //     if (snapshot.hasData) {
                      //       final dataSources = snapshot.data;
                      //       context
                      //           .read<DashboardProvider>()
                      //           .addTile(dataSources!);
                      //       // .addItem(dataSources!);
                      //     }
                      //   },
                      // ),
                      IconButton(
                        icon: const Icon(Icons.save),
                        tooltip: 'Save Dashboard',
                        onPressed: _saveDashboard,
                      ),
                      IconButton(
                          icon: const Icon(Icons.system_update_alt),
                          onPressed: _loadDashboard),
                    ],
                  ),
                  body: Consumer<DashboardProvider>(
                    builder: (context, dashboardProvider, child) {
                      int byMaxSize =
                          (MediaQuery.of(context).size.width ~/ maxTileSize)
                              .toInt();
                      int smartBySize = byMaxSize > 1
                          ? byMaxSize
                          : (MediaQuery.of(context).size.width ~/ minTileSize)
                              .toInt();
                      int numOfTilesInARow = max(
                          1,
                          min(
                              smartBySize,
                              max(
                                  context
                                      .read<DashboardProvider>()
                                      .tiles
                                      .length,
                                  2)));
                      return GridView.builder(
                        itemCount: dashboardProvider.tiles.length,
                        addAutomaticKeepAlives: true,
                        gridDelegate: SliverGridDelegateWithFixedCrossAxisCount(
                          mainAxisSpacing: 4,
                          crossAxisSpacing: 4,
                          crossAxisCount: numOfTilesInARow,
                        ),
                        itemBuilder: (BuildContext context, int index) {
                          return Stack(
                            children: <Widget>[
                              dashboardProvider.getTiles()[index],
                              Positioned(
                                right: 0,
                                child: IconButton(
                                  icon: const Icon(Icons.close),
                                  onPressed: () {
                                    dashboardProvider.removeTileAt(index);
                                  },
                                ),
                              ),
                            ],
                          );
                        },
                      );
                    },
                  ),
                );
              }
            });
      });
}
