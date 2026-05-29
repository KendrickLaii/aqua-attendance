import React from 'react';
import { View, Text, StyleSheet } from 'react-native';
import { getSavedUser, type User } from '../services/auth';

const THEME = { primary: '#160D47', bg: '#F4F5FA', success: '#56CA00', warning: '#FFB400', error: '#9d1c24' };

export default function QRDisplayScreen() {
  const [user, setUser] = React.useState<User | null>(null);

  React.useEffect(() => {
    getSavedUser().then(setUser);
  }, []);

  return (
    <View style={styles.container}>
      <View style={styles.card}>
        {user && (
          <>
            <Text style={styles.name}>{user.full_name || user.username}</Text>
            <View style={[styles.badge, { backgroundColor: user.role === 'student' ? THEME.success : '#16B1FF' }]}>
              <Text style={styles.badgeText}>{user.role}</Text>
            </View>
          </>
        )}
        <Text style={styles.iconBig}>🪪</Text>
        <Text style={styles.heading}>QR codes are managed per product</Text>
        <Text style={styles.body}>
          Open the web app's <Text style={styles.bold}>QR Codes</Text> page (admin only) to print
          or display a product's QR. Before scanning, choose Check In or Check Out on the Scan tab.
        </Text>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, justifyContent: 'center', alignItems: 'center', backgroundColor: THEME.bg, padding: 20 },
  card: {
    width: '100%', maxWidth: 360, backgroundColor: '#fff', borderRadius: 20,
    padding: 28, alignItems: 'center',
    shadowColor: '#000', shadowOffset: { width: 0, height: 4 }, shadowOpacity: 0.08, shadowRadius: 12, elevation: 4,
  },
  name: { fontSize: 20, fontWeight: '700', color: THEME.primary, marginBottom: 6 },
  badge: { paddingHorizontal: 12, paddingVertical: 3, borderRadius: 12, marginBottom: 20 },
  badgeText: { color: '#fff', fontSize: 12, fontWeight: '600', textTransform: 'uppercase' },
  iconBig: { fontSize: 56, marginVertical: 12 },
  heading: { fontSize: 16, fontWeight: '700', color: THEME.primary, marginBottom: 10, textAlign: 'center' },
  body: { fontSize: 13, color: '#666', textAlign: 'center', lineHeight: 18 },
  bold: { fontWeight: '700', color: THEME.primary },
});
