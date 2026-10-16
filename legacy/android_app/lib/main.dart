import 'package:flutter/material.dart';
import 'package:firebase_core/firebase_core.dart';
import 'package:firebase_database/firebase_database.dart';
import 'firebase_config.dart';

void main() async {
  WidgetsFlutterBinding.ensureInitialized();
  await Firebase.initializeApp(options: firebaseOptions);
  runApp(MyApp());
}

class MyApp extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'SM Scolers — Mobile',
      theme: ThemeData.dark(),
      home: HomePage(),
    );
  }
}

class HomePage extends StatefulWidget {
  @override
  _HomePageState createState() => _HomePageState();
}

class _HomePageState extends State<HomePage> {
  final DatabaseReference _logsRef = FirebaseDatabase.instance.ref(
    'attendance_logs',
  );
  Map<String, dynamic> _entries = {};
  bool _loading = true;

  @override
  void initState() {
    super.initState();
    _listen();
  }

  void _listen() {
    _logsRef.onValue.listen(
      (event) {
        final data = event.snapshot.value;
        setState(() {
          if (data is Map) {
            _entries = Map<String, dynamic>.from(data);
          } else {
            _entries = {};
          }
          _loading = false;
        });
      },
      onError: (err) {
        setState(() {
          _loading = false;
        });
        print('DB error: $err');
      },
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: Text('SM Scolers — Attendance Logs')),
      body: _loading
          ? Center(child: CircularProgressIndicator())
          : _entries.isEmpty
          ? Center(child: Text('No records found'))
          : ListView.builder(
              itemCount: _entries.keys.length,
              itemBuilder: (context, index) {
                final key = _entries.keys.elementAt(index);
                final item = Map<String, dynamic>.from(_entries[key]);
                return ListTile(
                  title: Text(item['name'] ?? 'Unknown'),
                  subtitle: Text(item['timestamp'] ?? ''),
                  trailing: Text(item['status']?.toString() ?? ''),
                );
              },
            ),
      floatingActionButton: FloatingActionButton(
        child: Icon(Icons.refresh),
        onPressed: () => setState(() {}),
      ),
    );
  }
}
